#This script creates a SQL version of the latest "Table List" for the American Community Survey
library(dplyr)
library(rvest)

# parameters to connect to SQL
sqlHost = "localhost"
sqlUserName = "sa"
sqlPassword = "yourStrong(!)Password"
sqlDefaultDb = "master"

# loop waiting for SQL Server database to become available
for (i in 1:60) {
    cn = tryCatch(
        # connect to SQL
        MsSqlTools::connectMsSqlSqlLogin(
            server = sqlHost, 
            user = sqlUserName, 
            password = sqlPassword, 
            database = sqlDefaultDb
        ), warning = function(e) {
            return(NA)
        }, error = function(e) {
            return(NA)
        }
    )

    suppressWarnings({
         if (is.na(cn)) {
            Sys.sleep(10)
        } else {
            break
        }
    })
   
}

suppressWarnings({
    if (is.na(cn)) {
        stop("could not connect to SQL Server")
    }
})

# control persistence of downloaded and extracted text files
persistTextFiles = FALSE

SqlTools::dbSendUpdate(cn, "USE EDWLandingZone")

outputDirectory = "/EDW/Data"

downloadErrors = dplyr::tibble(
  FileUrl=character(), 
  Error=character()
 )

# Query the table codebook to get a list of all base tables
baseTables = DBI::dbGetQuery(cn, "SELECT DISTINCT(TableID)
                                    FROM [EDWLandingZone].[Metadata].[TableCodebook]
                                    WHERE DataProductType = 'Detailed Table'
                                    AND TableID like 'B%'
                                    ")


for (i in 1:nrow(baseTables)) {
    currTableName = baseTables[i,"TableID"]
    for (year in 2008:2021) {
        currFileUrl = paste("https://api.census.gov/data/", year, "/acs/acs5?get=NAME,group(", currTableName , ")&for=county:*&key=", sep="")

        cat("Reading ", currFileUrl, "\n")
        
        tryCatch( { 
            #get the data as a df
            df <- jsonlite::fromJSON(currFileUrl) %>% as.data.frame
            df <- df %>% janitor::row_to_names(row_number = 1)
            df <- subset(df, select = -NAME)
            df$YEAR <- year
            
            currOutputFileName = paste(sep = "", outputDirectory, "/", currTableName,".csv")
            
            names(df)[names(df) == 'state'] <- 'STATE'
            
            #if the table exists, bulk insert new data
            if (DBI::dbExistsTable(cn, currTableName) == TRUE){ 
                
                rs <- DBI::dbGetQuery(cn, paste(sep="",
                                                "SELECT * FROM [EDWLandingZone].[ACS].",
                                                    currTableName))
                names(rs)[names(rs) == 'state'] <- 'STATE'
                names(rs)[names(rs) == 'county'] <- 'COUNTY'
                
                df <- df[names(rs)]
                
                #write to disk
                write.table(
                    df,
                    file = currOutputFileName,
                    sep = "\t",
                    na = "",
                    row.names = FALSE,
                    col.names = FALSE,
                    quote = FALSE)
                
                #bulk insert data
                insertStatement = paste(sep="",
                                    "BULK INSERT [EDWLandingZone].[ACS].",
                                    currTableName,
                                    " FROM '",
                                    currOutputFileName,
                                    "' WITH (KEEPNULLS, TABLOCK, ROWS_PER_BATCH=2000, FIRSTROW=1, FIELDTERMINATOR='\t')"
                )
                
                
                SqlTools::dbSendUpdate(cn, insertStatement)
                
                #shrink transaction log
                SqlTools::dbSendUpdate(cn, "DBCC SHRINKFILE(EDWLandingZone_log)")

                # issue checkpoint
                SqlTools::dbSendUpdate(cn, "CHECKPOINT")
                
            #if the table doesn't exist, create the schema
            }else {
                #get schema from variablecodebook
                codebookSchema = DBI::dbGetQuery(cn, paste("SELECT [Name],[PredicateType] FROM [EDWLandingZone].[Metadata].[VariableCodebook] WHERE TableID = '",currTableName,"'", sep=""))
                
                #edit schema to fit variablecodebook                
                createTableQuery = paste("CREATE TABLE [EDWLandingZone].[ACS].",
                                          currTableName,
                                          "(GEO_ID VARCHAR(256),",
                                          "NAME VARCHAR(256),",
                                          "STATE VARCHAR(256),",
                                          "COUNTY VARCHAR(256),",
                                          "YEAR INTEGER,",
                                          paste(codebookSchema[,1],codebookSchema[,2], collapse= ","),
                                          ")",sep = "")

                #create table
                SqlTools::dbSendUpdate(cn, createTableQuery)
                
                rs <- DBI::dbGetQuery(cn, paste(sep="",
                                                "SELECT * FROM [EDWLandingZone].[ACS].",
                                                    currTableName))

                names(rs)[names(rs) == 'state'] <- 'STATE'
                names(rs)[names(rs) == 'county'] <- 'COUNTY'
                
                df <- df[names(rs)]
                
                #bulk insert the data
                insertStatement = paste(sep="",
                                    "BULK INSERT [EDWLandingZone].[ACS].",
                                    currTableName,
                                    " FROM '",
                                    currOutputFileName,
                                    "' WITH (KEEPNULLS, TABLOCK, ROWS_PER_BATCH=2000, FIRSTROW=1, FIELDTERMINATOR='\t')"
                )
                
                SqlTools::dbSendUpdate(cn, insertStatement)
                
                indexStatement = paste(sep="",
                                    "CREATE CLUSTERED COLUMNSTORE INDEX ccix ON [EDWLandingZone].[ACS].",
                                    currTableName)

                SqlTools::dbSendUpdate(cn, indexStatement)
                
                #shrink transaction log
                SqlTools::dbSendUpdate(cn, "DBCC SHRINKFILE(EDWLandingZone_log)")

                # issue checkpoint
                SqlTools::dbSendUpdate(cn, "CHECKPOINT")
            }   
            }, error = function(e){NA}
        )
    }
}


#shrink transaction log
SqlTools::dbSendUpdate(cn, "DBCC SHRINKFILE(EDWLandingZone_log)")

# issue checkpoint
SqlTools::dbSendUpdate(cn, "CHECKPOINT")

# shutdown the database engine cleanly
SqlTools::dbSendUpdate(cn, "SHUTDOWN")
