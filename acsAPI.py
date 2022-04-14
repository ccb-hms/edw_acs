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
# from sqlalchemy import create_engine
# import pyodbc


def find_tables(year_range):
    # send an http request to the census website to collect all available table shells
    print(year_range)
    html_parser = etree.HTMLParser()
    web_page = requests.get('https://www.census.gov/programs-surveys/acs/technical-documentation/table-shells.2019.html')
    web_page_html_string = web_page.content.decode("utf-8")
    str_io_obj = StringIO(web_page_html_string)
    dom_tree = etree.parse(str_io_obj, parser=html_parser)
    link = dom_tree.xpath('//*[@name="2019 ACS Table List"]/@href')[0]

    # use pandas(pd) to read the csv file into a dataframe
    table_lst = pd.read_excel(link, engine='openpyxl')
    # transform the dataframe into a dictionary 
    table_lst = table_lst.to_dict("records")
    # the table_lst dictionary is a dict of ALL tables, but we only want the Base detailed tables, 
    # which contain the largest swath of data. These tables begin with a 'B'. Here we are creating
    # an empty dict 'tables' to later populate with only the tables beginning with B.
    tables = {}

    #loop through the larger table list, and append any Base tables to the filtered tables dict
    for i in table_lst:
        if i['Table ID'][0] == "B": 
            tables[i['Table ID']] = i['Table Title']
    get_acs_data(tables, year_range)

def get_acs_data(tables, years):
    # if the user enters a range, assign variables to the beginning and end of the range
    if "-" in years:
        years.replace(" ","").split("-")
        year1 = years[0]
        year2=years[1]
    # if the user enters a single year, assign year2 to be +1 year from the desired year, so the range function won't error out
    else:
        year1 = int(years)
        year2 = int(years)+1
    # loop through each year in the users defined range, then each table from the find_tables() function
    for year in range(year1, year2):
        #for table in tables:  
            # API request to get all zipcode tabulated data for the current year and table
            response = requests.get('https://api.census.gov/data/{year}/acs/acs5?get=NAME,group({table})&for=zip%20code%20tabulation%20area:*&key=62fade369e5f8276f58c592eed6a5a6e19bdbb3a'.format(year=year,table=table))
            if response.status_code != 200:
                # TODO log the error in a file
                pass
            else:
                # if the API call returns data, load it as a json, then use pandas to transform the data into a dataframe
                data = response.json()
                df = pd.DataFrame(data[1:], columns=data[0])
                # this API call is to get the human-readable version of all the columns per table.
                response = requests.get("https://api.census.gov/data/{year}/acs/acs5/groups/{table}.json".format(year=year,table=table))         
                cols = response.json()
                cols = cols['variables']
                ccols = {}
                # data manipulation, column renaming, null drops
                for i in cols:
                    ccols[i] = cols[i]['label'].replace("!!"," ")
                df.rename(columns = ccols, inplace=True)
                df = df.replace('ZCTA5 ', '', regex=True)
                df.columns = df.columns.str.title()
                df.columns = df.columns.str.replace(" ","")
                df.dropna(how='all', axis=1, inplace=True)
                #old csv export
                path = "/HostData"
                print(path+'/ACS_5Y_Estimates_{year}_{table}_{tablename}.csv'.format(year=year,table=table,tablename=tables[table].replace(" ","_").replace(",","").replace("(", "").replace(")","").replace("-","")))
                # df.to_csv(path+'/ACS_5Y_Estimates_{year}_{table}_{tablename}.csv'.format(year=year,table=table,tablename=tables[table].replace(" ","_").replace(",","").replace("(", "").replace(")","").replace("-","")), encoding='utf-8', index=False, sep ='\t')
                # filename = 'ACS_5Y_Estimates_{year}_{table}_{tablename}'.format(year=year,table=table,tablename=tables[table].replace(" ","_").replace(",","").replace("(", "").replace(")","").replace("-",""))

                # acs_ETL(df, filename)

# def acs_ETL(df, filename):
#     sql_tablename = filename
#     create = pd.io.sql.get_schema(df.reset_index(), filename)

# # TODO make sure the col type is varchar (or int / float / etc.)
#     # create text file
#     sql_create = open("sql_create.txt","a+")
#     sql_create.write(create+"\n")
#     sql_create.close()
#     # df.to_sql(filename, con=engine, if_exists = 'append', chunksize = 1000, index = False)

#     # python
#     # create sqlalchemy engine
#     # engine = create_engine("mssql+pyodbc://{user}:{pw}@{sv}:1433/{db}?driver=ODBC+DRIVER+17+for+SQL+Server"
#     #                    .format(user="sa",
#     #                            pw="sa",
#     #                            db="db_name",
#     #                            sv='192.168.86.39'))

#     # # Insert whole DataFrame into MySQL
#     # df.to_sql(filename, con=engine, if_exists = 'append', chunksize = 1000, index = False, dtype={col_name: NVARCHAR for col_name in df})

if __name__ == "__main__":
    year_range = str(sys.argv[1])
    find_tables(year_range)

# #TODO figure out how df.to_sql() works under the hood
# #TODO does this utilize the transaction log?? 

# tries:
# #
# connection.execute(table.insert().values(data))
# #
# #
# https://medium.com/analytics-vidhya/speed-up-bulk-inserts-to-sql-db-using-pandas-and-python-61707ae41990
# from sqlalchemy import event
# @event.listens_for(engine, "before_cursor_execute")
# def receive_before_cursor_execute(
#        conn, cursor, statement, params, context, executemany
#         ):
#             if executemany:
#                 cursor.fast_executemany = True

# df.to_sql(tbl, engine, index=False, if_exists="append", schema="dbo")
# #
# #
# import pyodbc 

# conn = pyodbc.connect('Driver={SQL Server};'
#                       'Server=server_name;'
#                       'Database=database_name;'
#                       'Trusted_Connection=yes;')

# cursor = conn.cursor()
# cursor.execute('SELECT * FROM table_name')

# for i in cursor:
#     print(i)
# #


#Thursday problem: why can't my code accept an input?
#How to parameterize it if it's running over ssh?
#Save as .txt not .csv to preserve the tab delimiting
