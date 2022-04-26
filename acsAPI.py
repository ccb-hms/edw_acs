#Author: Sam Pullman
#Agency: Center for Computational Biomedicine (CCB)
#Project: Exposome Data Warehouse - American Community Survey 5 Year Estimates API Download

import json
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

def find_tables(years, uid, pwd, ipaddress):
    # Connect to the master db and create the db for future use 
    driver = "ODBC Driver 17 for SQL Server"
    conn = pyodbc.connect(f"DRIVER={driver};SERVER={ipaddress};DATABASE=master;UID={uid};PWD={pwd}", autocommit=True)
    cursor = conn.cursor()
    drop_create_db = '''USE master;
                    ALTER DATABASE [AmericanCommunitySurvey] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
                    DROP DATABASE [AmericanCommunitySurvey] ;
                    CREATE DATABASE [AmericanCommunitySurvey] ;'''
    
    cursor.execute(drop_create_db)
    conn.commit()

    # Connect to the ACS db and create a fresh schema for each year:
    year1, year2 = year_split(years)
    conn = pyodbc.connect(f"DRIVER={driver};SERVER={ipaddress};DATABASE=AmericanCommunitySurvey;UID={uid};PWD={pwd}", autocommit=True)
    cursor = conn.cursor()

    for year in range(year1, year2):
        # Create schema
        year = str(year)
        schema = f'CREATE SCHEMA ACS_5Y_{year};'
        cursor.execute(schema)
        conn.commit()

    # Send an http request to the census website to collect all available table shells
    html_parser = etree.HTMLParser()
    web_page = requests.get('https://www.census.gov/programs-surveys/acs/technical-documentation/table-shells.2019.html', timeout=10)
    web_page_html_string = web_page.content.decode("utf-8")
    str_io_obj = StringIO(web_page_html_string)
    dom_tree = etree.parse(str_io_obj, parser=html_parser)
    link = dom_tree.xpath('//*[@name="2019 ACS Table List"]/@href')[0]

    #connect to the AmericanCommunitySurvey db
    conn = pyodbc.connect(f"DRIVER={driver};SERVER={ipaddress};DATABASE=AmericanCommunitySurvey;UID={uid};PWD={pwd}", autocommit=True)
    cursor = conn.cursor()

    # Use pandas(pd) to read the csv file of ACS tablenamesinto a dataframe
    table_lst = pd.read_excel(link, engine='openpyxl')

    # Export the csv to sql as a table legend
    legend = table_lst.to_csv('/HostData/Legend.csv', sep=',', encoding='utf-8', index=False)
    create = pd.io.sql.get_schema(table_lst, 'TableLegend')
    cursor.execute(create)
    conn.commit()

    bulk_insert = "BULK INSERT TableLegend FROM '" + '/HostData/Legend.csv' + "' WITH (TABLOCK, FIRSTROW=2, FIELDTERMINATOR = ',',ROWTERMINATOR = '\n');"
    cursor.execute(bulk_insert)
    conn.commit()

    # Transform the table_lst dataframe into a dictionary 
    table_lst = table_lst.to_dict("records")

    # The table_lst dictionary is a dict of ALL tables, but we only want the Base detailed tables, 
    # which contain the largest swath of data. These tables begin with a 'B'. Here we are creating
    # an empty dict 'tables' to later populate with only the tables beginning with B.
    tables = {}

    # Loop through the larger table list, and append any Base tables to the filtered tables dict
    for i in table_lst:
        if i['Table ID'][0] == "B": 
            tables[i['Table ID']] = i['Table Title']

    get_acs_data(tables, years=args.year, start=args.start, alone=args.alone)

def get_acs_data(tables, years, start, alone):
    # Set up logging
    logger = logging.getLogger('api_logger')
    # If the user entered a specific table (optional arg), filter out the one's we've already done. 
    filtered_tables = list(tables.keys())[list(tables.keys()).index(start):]

    # If the user enters a range, assign variables to the beginning and end of the range
    year1, year2 = year_split(years)

    # Loop through each year in the users defined range, and each table available in the API
    for year, table in product(range(year1, year2), tables):
        if table in filtered_tables:
            # API request to get all zipcode tabulated data for the current year and table
            print(f"{year} - {table}")
            try:
                response = requests.get(f'https://api.census.gov/data/{year}/acs/acs5?get=NAME,group({table})&for=zip%20code%20tabulation%20area:*&key=62fade369e5f8276f58c592eed6a5a6e19bdbb3a',timeout=100)            
                if response.status_code != 200:
                    logger.warning(f'https://api.census.gov/data/{year}/acs/acs5?get=NAME,group({table})&for=zip%20code%20tabulation%20area:*&key=62fade369e5f8276f58c592eed6a5a6e19bdbb3a')
                    pass
                else:
                    # If the API call returns data, load it as a json, then use pandas to transform the data into a dataframe
                    data = response.json()
                    df = pd.DataFrame(data[1:], columns=data[0])

                    # This API call is to get the human-readable version of all the columns per table.
                    response = requests.get(f"https://api.census.gov/data/{year}/acs/acs5/groups/{table}.json")         
                    cols = response.json()
                    cols = cols['variables']
                    ccols = {}

                    # Data manipulation, column renaming, null drops
                    for i in cols:
                        ccols[i] = cols[i]['label'].replace("!!"," ")

                    # Renaming columns from serial codes to their corresponding human-readable names    
                    df.rename(columns = ccols, inplace=True)

                    # Remove "ZCTA " from the first column values. Ex. "ZCTA 90210" --> "90210"
                    df = df.replace('ZCTA5 ', '', regex=True)

                    # Camel-case all column headers
                    df.columns = df.columns.str.title()
                    df.columns = df.columns.str.replace(" ","")

                    # Fill NaN values with nulls
                    df.fillna("",inplace=True)

                    # Drop duplicated columns
                    df = df.loc[:,~df.columns.duplicated()]

                    # Write file to the shared directory, and call ETL function
                    path = "/HostData/"
                    filename = 'ACS_5Y_Estimates_{year}_{table}'.format(year=year,table=table)
                    filepath = path + filename + ".txt"
                    df.to_csv(filepath, encoding='utf-8', index=False, sep =',')
                    acs_ETL(df, filename, filepath, year, table, uid=args.uid, pwd=args.pwd, ipaddress=args.ipaddress)

            except Exception as e:
                logger.warning(e)

            # Check if this is supposed to be a one-off table pull or not
            if not alone:
                break


def acs_ETL(df, tablename, filepath, year, table, uid, pwd, ipaddress):
    # Set up logging
    logger = logging.getLogger('sql_logger')
    
    # Connect into DB Server
    driver = "ODBC Driver 17 for SQL Server"
    conn = pyodbc.connect(f"DRIVER={driver};SERVER={ipaddress};DATABASE=AmericanCommunitySurvey;UID={uid};PWD={pwd}", autocommit=True)
    cursor = conn.cursor()

    # Modify the create statement with corrected datatypes
    create = pd.io.sql.get_schema(df, f'ACS_5Y_{year}.{table}')

    create = create.replace("TEXT", "NVARCHAR(MAX)")
    create = create.split(",")
    for i in range(1, len(create)-1):
        if "Estimate" in create[i] or "Margin" in create[i]:
            if "Annotation" not in create[i]:
                create[i] = create[i].replace("NVARCHAR(MAX)", "INT")
    create = ','.join(create)

    # Execute table creation and bulk insert
    try:
        cursor.execute(create)
        conn.commit()

        bulk_insert = "BULK INSERT " + f'[AmericanCommunitySurvey].[dbo].[ACS_5Y_{year}.{table}]' + " FROM '" + filepath + "' WITH (TABLOCK, FIRSTROW=2, FIELDTERMINATOR = ',',ROWTERMINATOR = '\n');"
        cursor.execute(bulk_insert)
        conn.commit()

    except Exception as e:
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


if __name__ == "__main__":
    # Construct the argument parser
    parser = argparse.ArgumentParser()

    # Add the arguments to the parser
    parser.add_argument('-y', '--year', type= str, required=True, action="store", help='the year (format YYYY) or years (format YYYY-YYYY) you would like to pull data for. This should be a str.')
    parser.add_argument('-s', '--start', type= str, required=False, action="store", default = 'B01001', help='If you would like to pull a single table, or start the pull from a specific table, define it here as a string, ex. "B01001".')
    parser.add_argument('-a', '--alone', required=False, action="store_false", help='If you would like to pull a single table, use this option.')
    parser.add_argument('-u', '--uid', type= str, required=True, action="store", help='User ID for the DB server')
    parser.add_argument('-p', '--pwd', type= str, required=True, action="store", help='Password for the DB server')
    parser.add_argument('-ip', '--ipaddress', type= str, required=True, action="store", help='The network address of the DB server')    

    # Print usage statement
    if len(sys.argv) < 2:
        parser.print_help()
        parser.print_usage()
        parser.exit()
    
    args = parser.parse_args()

    # Set up logging configs
    logging.basicConfig(filename='/HostData/logging.log',level=logging.INFO, format='%(asctime)s | %(name)s | %(levelname)s | %(message)s')

    # I want to have logging from two separate functions, so here I'm defining the separate handlers and loggers
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
                'filename': '/HostData/api.txt'
            },
            'sql_calls': {
                'class' : 'logging.FileHandler',
                'formatter': 'simple_formatter',
                'filename': '/HostData/sql.txt'
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
    
    # Call the first function
    find_tables(years=args.year, uid=args.uid, pwd=args.pwd, ipaddress=args.ipaddress)
    
    # When the data pull is complete, write the logs to a csv file for easy reviewing
    with open('/HostData/logging.log', 'r') as logfile, open('/HostData/LOGFILE.csv', 'w') as csvfile:
        reader = csv.reader(logfile, delimiter='|')
        writer = csv.writer(csvfile, delimiter=',',)
        writer.writerow(['EventTime', 'Origin', 'Level', 'Message'])
        writer.writerows(reader)
    
    # Delete the two txt files created by the logging. This step isn't necessary, but I like to clean
    # up the dir when I'm done.
    os.remove('/HostData/sql.txt')
    os.remove('/HostData/api.txt')
