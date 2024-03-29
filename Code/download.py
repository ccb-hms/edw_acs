#Author: Sam Pullman
#Agency: Center for Computational Biomedicine (CCB)
#Project: Exposome Data Warehouse - American Community Survey 5 Year Estimates API Download

# Project imports
import json
import traceback
import pandas as pd
import sys
import openpyxl
import requests
from lxml import etree
from io import StringIO
import pyodbc
from itertools import product
import argparse
import sys
import logging
import logging.config
import csv
import os
import numpy as np
from csv import writer

def find_tables(years, uid, pwd, ipaddress, start, alone, apikey, geo, cleanup, restart):
    # Send an http request to the census website to collect all available table shells
    html_parser = etree.HTMLParser()
    web_page = requests.get('https://www2.census.gov/programs-surveys/acs/tech_docs/table_shells/table_lists/2022_DataProductList.xlsx', timeout=10)
    web_page_html_string = web_page.content.decode("utf-8")
    str_io_obj = StringIO(web_page_html_string)
    dom_tree = etree.parse(str_io_obj, parser=html_parser)
    link = dom_tree.xpath('//*[@name="2019 ACS Table List"]/@href')[0]

    # Use pandas(pd) to read the csv file of ACS tablenamesinto a dataframe
    table_lst = pd.read_excel(link, engine='openpyxl')
    table_lst['Table Universe'] = table_lst['Table Universe'].str.replace('Universe: ','', regex=True)

    # Data cleaning function
    table_lst = clean(table_lst)

    # Export the csv to sql as a table legend 
    legend = table_lst.to_csv('/HostData/TableLegend.csv', sep=',', encoding='utf-8', index=False)

    # Year splitting function that returns the users' command line input as two numbers.
    year1, year2 = year_split(years)

    for year in range(year1, year2):
        # Create schema
        year = str(year)
        print(os.getcwd())
        bulk_insert = "BULK INSERT " + f'[AmericanCommunitySurvey].[{year}_{geo}].[TableLegend]' + "FROM '" + '/HostData/TableLegend.csv' + "' WITH (TABLOCK, FORMAT = 'CSV', FIRSTROW=2, FIELDTERMINATOR = ',',ROWTERMINATOR = '\n');"
        sql_server(bulk_insert, 'AmericanCommunitySurvey', ipaddress=args.ipaddress, uid=args.uid, pwd=args.pwd) 

    # Transform the table_lst dataframe into a dictionary 
    table_lst = table_lst.to_dict("records")

    # The table_lst dictionary is a dict of ALL tables, but we only want the Base detailed tables, 
    # which contain the largest swath of data. These tables begin with a 'B'. Here we are creating
    # an empty dict 'tables' to later populate with only the tables beginning with B.
    global tables
    tables = {}

    # Loop through the larger table list, and append any Base tables to the filtered tables dict
    for i in table_lst:
        if i['TableID'][0] == "B": 
            tables[i['TableID']] = i['TableTitle']

def create_schema(years, uid, pwd, ipaddress, start, alone, apikey, geo, cleanup, restart):
    logger = logging.getLogger('api_logger')
    # Connect to the ACS db and create a fresh schema for each year:
    year1, year2 = year_split(years)

    for year in range(year1, year2):
        # Create schema
        try:
            year = str(year)

            schema = f'''IF (NOT EXISTS (SELECT * FROM sys.schemas WHERE name = '{year}_{geo}')) 
            BEGIN
            EXEC ('CREATE SCHEMA [{year}_{geo}] AUTHORIZATION [dbo]')
            END'''

            sql_server(schema, 'AmericanCommunitySurvey', ipaddress, uid, pwd)
            
            # Create variablelabel table for all column names in human-readable format
            create_variablelabel = "CREATE TABLE "+ f'[AmericanCommunitySurvey].[{year}_{geo}].[VariableLabels]' + "(TableName VARCHAR(MAX), ColumnID VARCHAR(MAX),Label VARCHAR(MAX),Concept VARCHAR(MAX),PredicateType VARCHAR(MAX));"
            sql_server(create_variablelabel, "AmericanCommunitySurvey", ipaddress, uid, pwd)

            # Create table legends
            create_legend = "CREATE TABLE "+ f'[AmericanCommunitySurvey].[{year}_{geo}].[TableLegend]' + "(TableName VARCHAR(MAX), TableTitle VARCHAR(MAX), TableUniverse VARCHAR(MAX));"
            sql_server(create_legend, "AmericanCommunitySurvey", ipaddress, uid, pwd)

        except pyodbc.Error as e:
            traceback.print_exc()
            logger.warning(e)
            pass

# This function only executes if the user has NOT included the --restart option in the command line.
def create_db(ipaddress, uid, pwd):
    # If the AmericanCommunitySurvey db has already been created, drop it and re-create it blank
    drop_create_db = '''USE master;
                    ALTER DATABASE [AmericanCommunitySurvey] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
                    DROP DATABASE [AmericanCommunitySurvey] ;
                    CREATE DATABASE [AmericanCommunitySurvey] ;'''

    # Call the sql_server function to connect to the db and execute the query
    sql_server(drop_create_db, 'master', ipaddress, uid, pwd)


def get_acs_data(years, uid, pwd, ipaddress, start, alone, apikey, geo, cleanup, restart):
    # Set up logging
    logger = logging.getLogger('api_logger')
    # If the user entered a specific table (optional arg), filter out the one's we've already done. 
    filtered_tables = list(tables.keys())[list(tables.keys()).index(start):]

    # If the user enters a range, assign variables to the beginning and end of the range
    year1, year2 = year_split(years)

    # String formatting for the API url
    if geo == "ZCTA":
        api_geo = "zip%20code%20tabulation%20area:*"
    if geo == "STATE":
        api_geo = "state:*"
    
    if geo == "COUNTY":
        api_geo = "county:*"

    if "BLOCKGROUP" in geo:
        state_codes = {"01":"AL","02":"AK","03":"AZ","04":"AR","05":"CA","06":"CO","07":"CT","08":"DE","09":"DC","10":"FL","11":"GA","12":"HA","13":"ID","14":"IL","15":"IN","16":"IO","17":"KS","18":"KY","19":"LO","20":"ME","21":"MD","22":"MA","23":"MI","24":"MN","25":"MS","26":"MO","27":"MT","28":"NE","29":"NV","30":"NH","31":"NJ","32":"NM","33":"NY","34":"NC","35":"ND","36":"OH","37":"OK","38":"OR","39":"PN","40":"RI","41":"SC","42":"SD","43":"TN","44":"TX","45":"UT","46":"VT","47":"VA","48":"WA","49":"WV","50":"WI","51":"WY"}    
        state_code = [key for key,value in state_codes.items() if value == geo.replace("BLOCKGROUP_","")]
        api_geo = f"block%20group:*&in=state:{state_code[0]}%20county:*"

    # If the user included the --alone argument in the command line, only the selected table will be downloaded.
    if not alone:
        filtered_tables = [start]

    # Loop through each year in the users defined range, and each table available in the API
    for year, table in product(range(year1, year2), tables):
        if table in filtered_tables:
            # API request to get all zipcode tabulated data for the current year and table
            print(f"{year} - {geo} - {table}")

            try:    
                response = requests.get(f'https://api.census.gov/data/{year}/acs/acs5?get=NAME,group({table})&for={api_geo}&key={apikey}',timeout=100)            

                if response.status_code != 200:
                    logger.warning(f'https://api.census.gov/data/{year}/acs/acs5?get=NAME,group({table})&for={api_geo}&key={apikey}')
                    pass
                
                else:
                    # If the API call returns data, load it as a json, then use pandas to transform the data into a dataframe
                    data = response.json()
                    df = pd.DataFrame(data[1:], columns=data[0])
                    df = clean(df)
                    
                    # This API call is to get the human-readable version of all the columns per table.
                    response = requests.get(f"https://api.census.gov/data/{year}/acs/acs5/groups/{table}.html")         
                    cols = pd.read_html(response.text)[0]
                    variablelabels(cols, table, year, geo)

                    # Write the df to a .csv file in the shared directory, then ETL the file.
                    path = "/HostData/"
                    filename = f'ACS_5Y_Estimates_{year}_{geo}_{table}'
                    filepath = path + filename + ".txt"
                    df.to_csv(filepath, encoding='utf-8', index=False, sep=',')

                    # Call the ETL function
                    acs_ETL(df, filename, filepath, year, table, geo, uid=args.uid, pwd=args.pwd, ipaddress=args.ipaddress)

                    # If the user selected --cleanup in the command line options, the .csv file will be deleted from the directory.
                    if not cleanup:
                        os.remove(filepath)
                    else:
                        pass

                    # Issue SQL checkpoint
                    checkpoint = 'CHECKPOINT'
                    sql_server(checkpoint, 'AmericanCommunitySurvey', ipaddress, uid, pwd)

            except Exception as e:
                traceback.print_exc()
                logger.warning(e)
 


def variablelabels(cols, table, year, geo):
    # For each table, create a crosswalk table for the human-readable version of the column names

    pd.options.mode.chained_assignment = None  # default='warn'

    cols = cols[['Name','Label','Concept','Predicate Type']]
    cols.insert(0, 'TableName', table)
    cols = cols.replace('!!', ' ', regex=True)
    cols['Label'] = cols['Label'].str.title()
    cols['Label'] = cols['Label'].str.replace(' ', '', regex=True)
    cols['Predicate Type'] = cols['Predicate Type'].str.replace('string', 'VARCHAR(MAX)', regex=True)
    cols['Predicate Type'] = cols['Predicate Type'].str.replace('int', 'INTEGER', regex=True)

    cols = cols.rename({'Name': 'ColumnID', 'Predicate Type':'PredicateType'}, axis=1)
    cols.drop(cols.tail(1).index,inplace=True)

    # Export the csv to sql as a table legend
    variablelabels_csv = cols.to_csv('/HostData/variablelabels.csv', sep=',', encoding='utf-8', index=False)
    bulk_insert = "BULK INSERT " + f'[AmericanCommunitySurvey].[{year}_{geo}].[VariableLabels]' + "FROM '" + '/HostData/variablelabels.csv' + "' WITH (TABLOCK, FORMAT = 'CSV', FIRSTROW=2, FIELDTERMINATOR = ',',ROWTERMINATOR = '\n');"
    sql_server(bulk_insert, 'AmericanCommunitySurvey', ipaddress=args.ipaddress, uid=args.uid, pwd=args.pwd) 


def clean(df):
    # Remove "ZCTA " from the first column values. Ex. "ZCTA 90210" --> "90210"
    df = df.replace('ZCTA5 ', '', regex=True)   

    # Fill NaN values with nulls
    df.fillna("",inplace=True)

    # Drop duplicated columns
    df = df.loc[:,~df.columns.duplicated()]

    # Remove spaces from names
    df.columns = df.columns.str.replace(' ', '')

    if 'TableUniverse' in df.columns:
        df = df.drop(['Year'], axis=1)
        df['TableUniverse'] = df['TableUniverse'].str.replace('"','', regex=True)
        df['TableUniverse'] = df['TableUniverse'].str.replace(',','-', regex=True)    
        df['TableTitle'] = df['TableTitle'].str.replace('"','', regex=True)
        df['TableTitle'] = df['TableTitle'].str.replace(',','-', regex=True)

    return df


def acs_ETL(df, tablename, filepath, year, table, geo, uid, pwd, ipaddress):
    # Set up logging
    logger = logging.getLogger('sql_logger')

    # Modify the create statement with corrected datatypes
    create = pd.io.sql.get_schema(df, f'[AmericanCommunitySurvey].[{year}_{geo}].[{table}]')
    create = create.replace('"','',2)
    create = create.replace("TEXT", "|")
    create = create.replace("|", "VARCHAR(MAX)",1)

    create = create.split(",")

    for i in range(1, len(create)-1):
        if create[i][-4] == "E" or create[i][-4] == "M":
            create[i] = create[i].replace("|", "INTEGER")
        else:
            create[i] = create[i].replace("|", "VARCHAR(MAX)")      

    create = ','.join(create)
    create = create.replace("|", "VARCHAR(MAX)")

    # Execute table creation and bulk insert
    try:
        sql_server(create, 'AmericanCommunitySurvey', ipaddress, uid, pwd)
        
        bulk_insert = "BULK INSERT " + f'[AmericanCommunitySurvey].[{year}_{geo}].[{table}]' + " FROM '" + filepath + "' WITH (TABLOCK, FORMAT = 'CSV', FIRSTROW=2, FIELDTERMINATOR = ',',ROWTERMINATOR = '\n');"
                                       
        sql_server(bulk_insert, 'AmericanCommunitySurvey', ipaddress, uid, pwd)

    except Exception as e:
        # Some tables have >1024 columns. Here we are catching those and modifying their CREATE statement so as to store them as wide tables with sparse columns.
        if "exceeds the maximum of 1024 columns" in str(e):
            # Cast all Varchar columns as sparse varchars
            create = create.replace("VARCHAR(MAX)", "VARCHAR(MAX) SPARSE NULL")
            
            # Cast all int columns as sparse ints
            create = create.replace("INTEGER", "INTEGER SPARSE NULL")
            
            # SpecialPurposeColumns wide table definition
            create = create[:-2] + ',\n "SpecialPurposeColumns" XML COLUMN_SET FOR ALL_SPARSE_COLUMNS);'
            
            # Create the table with the updated Create query
            sql_server(create, 'AmericanCommunitySurvey', ipaddress, uid, pwd)

            # To fill the wide table with the data, rather than INSERTING all the null data, 
            # we delete the columns with null data, and only INSERT data that is not null.
            # This way, our INSERT statement isn't 1000+ columns long, when only 3 columns actually contain data.
            df.replace('', np.nan, inplace=True)
            df = df.dropna(axis='columns', how='all')
            cols = str(df.columns.to_list()).replace("[","").replace("]","").replace("'","")

            for row in df.to_numpy().tolist():
                if "'" in row[0]:
                    row[0] = row[0].replace("'","''")
                values = str(row).replace("[","").replace("]","").replace('"',"'")
                insert ="INSERT " + f'[AmericanCommunitySurvey].[{year}_{geo}].[{table}] ' +  "(" + cols + ")" + "VALUES (" + values + ");"  
                sql_server(insert, 'AmericanCommunitySurvey', ipaddress, uid, pwd)

        else:
            traceback.print_exc()
            logger.warning(e)


def year_split(years):
    # If the user enters a range, assign variables to the beginning and end of the range
    if "-" in years:
        years = years.replace(" ","").split("-")
        year1 = int(years[0])
        year2=int(years[1])

    # If the user enters a single year, assign year2 to be +1 year from the desired year, so the range function won't error out
    else:
        year1 = int(years)
        year2 = int(years)+1

    return(year1, year2)

def sql_server(query, db, ipaddress, uid, pwd):
    # Connect to SQL Server and execute a query
    conn = pyodbc.connect(f"DRIVER=ODBC Driver 17 for SQL Server;SERVER={ipaddress};DATABASE={db};UID={uid};PWD={pwd}", autocommit=True)
    cursor = conn.cursor()
    cursor.execute(query)
    conn.commit()

    
if __name__ == "__main__":
    # Construct the argument parser
    parser = argparse.ArgumentParser()

    # Add the command line arguments to the parser
    parser.add_argument('-y', '--year', type= str, required=True, action="store", help='The year (format "YYYY"|]) or years (format "YYYY-YYYY") to download data for. This should be a str.')
    parser.add_argument('-s', '--start', type= str, required=False, action="store", default = 'B01001', help='To pull a single table, or start the pull from a specific table, define it here as a string, ex. "B01001".')
    parser.add_argument('-a', '--alone', required=False, action="store_false", help='This option allows for the selection of a single table to be downloaded.')
    parser.add_argument('-u', '--uid', type= str, required=True, action="store", help='User ID for the DB server')
    parser.add_argument('-p', '--pwd', type= str, required=True, action="store", help='Password for the DB server')
    parser.add_argument('-i', '--ipaddress', type= str, required=True, action="store", help='The network address of the DB server')    
    parser.add_argument('-k', '--apikey', type= str, required=True, action="store", help='The API key to access the Census.gov API. Request a free API key here: https://api.census.gov/data/key_signup.html')    
    parser.add_argument('-z', '--zcta', required=False, action="store_false", help='This option allows for the selection of the ZCTA geographical rollup.')
    parser.add_argument('-st', '--state', required=False, action="store_false", help='This option allows for the selection of the State geographical rollup.')
    parser.add_argument('-c', '--county', required=False, action="store_false", help='This option allows for the selection of the County geographical rollup.')
    parser.add_argument('-b', '--blockgroup', required=False, action="store_false", help='This option allows for the selection of the block group level geographical rollup.')    
    parser.add_argument('-r', '--restart', required=False, action="store_false", help='This option allows for adding data without deleting previously collected data. Useful for when a scrape fails and you want to pick up at a certain point.')
    parser.add_argument('-cl', '--cleanup', required=False, action="store_false", help='This option allows for the cleanup of the host directory, to save disk space.')

    # Print usage help statement
    if len(sys.argv) < 2:
        parser.print_help()
        parser.print_usage()
        parser.exit()
    
    args = parser.parse_args()

    # Set up logging configs
    logging.basicConfig(filename='/HostData/logging.log',level=logging.INFO, format='%(asctime)s | %(name)s | %(levelname)s | %(message)s')

    # I want to have logging from two separate functions, so here I'm defining the separate handlers and loggers for the different functions they'll be used in
    logging.config.dictConfig({
        'version': 1,
        'formatters': {
            'simple_formatter': {
                'format': '%(asctime)s | %(name)s | %(levelname)s | %(message)s'
            }
        },
        'handlers': {
            'api_calls': {
                'class' : 'logging.FileHandler',
                'formatter': 'simple_formatter',
                'filename': '/HostData/api_log.txt'
            },
            'sql_calls': {
                'class' : 'logging.FileHandler',
                'formatter': 'simple_formatter',
                'filename': '/HostData/sql_log.txt'
            }
        },
        'loggers': {
            'api_logger': {
                'handlers': ['api_calls']
            },
            'sql_logger': {
                'handlers': ['sql_calls']
            }
        }
    })
    
    # First line of the logs
    logging.info(f'Starting data pull for {args.year}')
    
    # If the user has included the --restart option in the command line, 
    # the db will not recreate, so it can be appended to rather than replacing old data.
    if args.restart:
        create_db(ipaddress=args.ipaddress, uid=args.uid, pwd=args.pwd)
    else:
        pass
    # Organizing what geographical rollups the user chose
    geos = {"ZCTA":args.zcta, "STATE":args.state, "COUNTY":args.county, "BLOCKGROUP":args.blockgroup}
    geos = [x for x in geos if geos[x]==False]

    # If the user didn't specify any rollups, all are chosen.
    if len(geos) == 0:
        geos = ["ZCTA", "STATE", "COUNTY", "BLOCKGROUP"]

    if "BLOCKGROUP" in geos and len(geos) > 0:
        
        # Create census block group state mappings     
        state_codes = [ 'AK', 'AL', 'AR', 'AZ', 'CA', 'CO', 'CT', 'DC', 'DE', 'FL', 'GA',
            'HI', 'IA', 'ID', 'IL', 'IN', 'KS', 'KY', 'LA', 'MA', 'MD', 'ME',
            'MI', 'MN', 'MO', 'MS', 'MT', 'NC', 'ND', 'NE', 'NH', 'NJ', 'NM',
            'NV', 'NY', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX',
            'UT', 'VA', 'VT', 'WA', 'WI', 'WV', 'WY']

        blockstring = 'BLOCKGROUP_'

        state_geos = [f"{blockstring}{state}" for state in state_codes]

        for f, rollup in product([create_schema, find_tables, get_acs_data], state_geos):
            f(years=args.year, uid=args.uid, pwd=args.pwd, ipaddress=args.ipaddress, start=args.start, alone=args.alone, apikey=args.apikey, geo=rollup, cleanup=args.cleanup, restart=args.restart)

        geos.remove("BLOCKGROUP")

    if len(geos)>0:
        # For each geographical rollup, execute create_schema first, then find_tables, then get_acs_data. All functions include the command line arguments.
        for f, rollup in product([create_schema, find_tables, get_acs_data], geos):
            f(years=args.year, uid=args.uid, pwd=args.pwd, ipaddress=args.ipaddress, start=args.start, alone=args.alone, apikey=args.apikey, geo=rollup, cleanup=args.cleanup, restart=args.restart)

    # When the data pull is complete, write the logs to a csv file for easy reviewing
    with open('/HostData/logging.log', 'r') as logfile, open('/HostData/LOGFILE.csv', 'w') as csvfile:
        reader = csv.reader(logfile, delimiter='|')
        writer = csv.writer(csvfile, delimiter=',',)
        writer.writerow(['EventTime', 'Origin', 'Level', 'Message'])
        writer.writerows(reader)


# Example command line inputs, in order without instructions. 
# It is not recommended to use these without thoroughly reading the documentation first,
# but once you've done it a few times I find having these shortcuts is helpful. 
# Thanks for using! -Sam

# docker build -t edw_acs .

# docker run \
# -e "ACCEPT_EULA=Y" \
# -e "SA_PASSWORD=Str0ngp@ssworD" \
# -p 1433:1433 \
# --platform linux/amd64 \
# --name sql1 \
# --hostname sql1 \
# -v ~/Desktop/:/HostData \
# -v /Users/Sam/Desktop/sqldata1:/var/opt/mssql \
# -d \
# --rm \
# mcr.microsoft.com/mssql/server:2019-latest
 
#  docker \
#  run \
#      --rm \
#      --platform linux/amd64 \
#      --name edw_acs \
#      -d \
#      -v /Users/Sam/Desktop/:/HostData \
#      -p 2200:22 \
#      -e 'CONTAINER_USER_USERNAME=test' \
#      -e 'CONTAINER_USER_PASSWORD=test' \
#      edw_acs 

# ssh test@localhost -p 2200 -Y -o GlobalKnownHostsFile=/dev/null -o UserKnownHostsFile=/dev/null \ python3 -u < edw_acs.py - "--year 2020 --uid sa --pwd Str0ngp@ssworD --ipaddress 172.17.0.2 --apikey ABCDEFGHIJK"
