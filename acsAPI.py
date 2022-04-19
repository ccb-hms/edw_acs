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

def find_tables(year_range, start="B01001", multi=True):
    # Send an http request to the census website to collect all available table shells
    html_parser = etree.HTMLParser()
    web_page = requests.get('https://www.census.gov/programs-surveys/acs/technical-documentation/table-shells.2019.html', timeout=10)
    web_page_html_string = web_page.content.decode("utf-8")
    str_io_obj = StringIO(web_page_html_string)
    dom_tree = etree.parse(str_io_obj, parser=html_parser)
    link = dom_tree.xpath('//*[@name="2019 ACS Table List"]/@href')[0]

    # Use pandas(pd) to read the csv file into a dataframe
    table_lst = pd.read_excel(link, engine='openpyxl')

    # Transform the dataframe into a dictionary 
    table_lst = table_lst.to_dict("records")

    # The table_lst dictionary is a dict of ALL tables, but we only want the Base detailed tables, 
    # which contain the largest swath of data. These tables begin with a 'B'. Here we are creating
    # an empty dict 'tables' to later populate with only the tables beginning with B.
    tables = {}

    # Loop through the larger table list, and append any Base tables to the filtered tables dict
    for i in table_lst:
        if i['Table ID'][0] == "B": 
            tables[i['Table ID']] = i['Table Title']

    get_acs_data(tables, year_range, start, multi)

def get_acs_data(tables, years, start="B01001", multi=True):
    # If the user entered a specific table (optional arg), filter out the one's we've already done. 
    filtered_tables = list(tables.keys())[list(tables.keys()).index(start):]

    # If the user enters a range, assign variables to the beginning and end of the range
    if "-" in years:
        years = years.replace(" ","").split("-")
        year1 = int(years[0])
        year2=int(years[1])
    # If the user enters a single year, assign year2 to be +1 year from the desired year, so the range function won't error out
    else:
        year1 = int(years)
        year2 = int(years)+1

    # Loop through each year in the users defined range, and each table available in the API
    failed_apis = open("/HostData/failed_api_calls.txt", "a")

    for year, table in product(range(year1, year2), tables):
        if table in filtered_tables:
            if multi == False:
                table = start
            # API request to get all zipcode tabulated data for the current year and table
            print(f"{year} - {table}")
            try:
                response = requests.get(f'https://api.census.gov/data/{year}/acs/acs5?get=NAME,group({table})&for=zip%20code%20tabulation%20area:*&key=62fade369e5f8276f58c592eed6a5a6e19bdbb3a',timeout=10)            
                if response.status_code != 200:
                    failed_apis.write(f"https://api.census.gov/data/{year}/acs/acs5?get=NAME,group({table})&for=zip%20code%20tabulation%20area:*&key=62fade369e5f8276f58c592eed6a5a6e19bdbb3a\n")
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
                    acs_ETL(df, filename, filepath)
                    if multi == False:
                        exit
            except Exception as e:
                failed_get_acs_data = open("/HostData/failed_get_acs_data.txt", "a")
                failed_get_acs_data.write(\n filename)
                failed_get_acs_data.write('\n ERROR - %s' % e)
                failed_get_acs_data.close()

def acs_ETL(df, filename, filepath):

    # Insert whole DataFrame into MySQL
    conn = pyodbc.connect("DRIVER={ODBC Driver 17 for SQL Server};SERVER=172.17.0.2, 1433;DATABASE=master;UID=sa;PWD=<YourStrong@Passw0rd>", autocommit=True)
    cursor = conn.cursor()

    # Create schema, edit text fields to nvarchar
    create = pd.io.sql.get_schema(df, filename)
    create = create.replace("TEXT", "NVARCHAR(MAX)")

    # Execute table creation and bulk insert
    try:
        cursor.execute(create)
        conn.commit()

        bulk_insert = "BULK INSERT " + filename + " FROM '" + filepath + "' WITH (TABLOCK, FIRSTROW=2, FIELDTERMINATOR = ',',ROWTERMINATOR = '\n');"
        cursor.execute(bulk_insert)
        conn.commit()

    except Exception as e:
        failed_sql = open("/HostData/failed_sql.txt", "a")
        failed_sql.write('\n\n ERROR - %s' % e)
        failed_sql.close()

if __name__ == "__main__":
    year_range = str(sys.argv[1])
    
    if len(sys.argv) > 2:
        start = str(sys.argv[2])
        if len(sys.argv) > 3:
            multi = str(sys.argv[3])
            find_tables(year_range, start, multi)
        else:
            find_tables(year_range, start)
    else:
        find_tables(year_range)
