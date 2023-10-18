#This script creates a SQL version of the latest "Table List" for the American Community Survey


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


# create landing zone for the raw data, set recovery mode to simple
SqlTools::dbSendUpdate(cn, "CREATE DATABASE EDWLandingZone")
SqlTools::dbSendUpdate(cn, "ALTER DATABASE [EDWLandingZone] SET RECOVERY SIMPLE")
SqlTools::dbSendUpdate(cn, "USE EDWLandingZone")
SqlTools::dbSendUpdate(cn, "CREATE SCHEMA Metadata")
SqlTools::dbSendUpdate(cn, "CREATE SCHEMA ACS")


SqlTools::dbSendUpdate(cn, "USE EDWLandingZone")


outputDirectory = "/EDW/Data"


downloadErrors = dplyr::tibble(
  FileUrl=character(), 
  Error=character()
 )


# Create the TableCodebook
currFileUrl = "https://www2.census.gov/programs-surveys/acs/tech_docs/table_shells/table_lists/2022_DataProductList.xlsx"
cat("reading ", currFileUrl, "\n")

currTemp = tempfile()

utils::download.file(
    url = currFileUrl, 
    destfile = currTemp
)

z = readxl::read_excel(currTemp)

currOutputFileName = paste(sep = "/", outputDirectory, "TableCodebook.csv")

#insert the table as Metadata.TableCodebook
write.table(
     z,
     file = currOutputFileName,
     sep = "/t",
     na = "",
     row.names = FALSE,
     col.names = FALSE,
     quote = FALSE)

# generate SQL table definitions from column types in tibbles
createTableQuery = DBI::sqlCreateTable(DBI::ANSI(), paste("Metadata", "TableCodebook", sep="."), z)

# change TEXT to VARCHAR(256)
createTableQuery = gsub(createTableQuery, pattern = "\" TEXT", replace = "\" VARCHAR(256)", fixed = TRUE)

# change DOUBLE to float
createTableQuery = gsub(createTableQuery, pattern = "\" DOUBLE", replace = "\" float", fixed = TRUE)

# remove double quotes, which interferes with the schema specification
createTableQuery = gsub(createTableQuery, pattern = '"', replace = "", fixed = TRUE)

# fix column names
createTableQuery = gsub(createTableQuery, pattern = 'Data Product Type', replace = "DataProductType", fixed = TRUE)
createTableQuery = gsub(createTableQuery, pattern = 'Table Universe', replace = "TableUniverse", fixed = TRUE)
createTableQuery = gsub(createTableQuery, pattern = 'Table Title', replace = "TableTitle", fixed = TRUE)
createTableQuery = gsub(createTableQuery, pattern = 'Table ID', replace = "TableID", fixed = TRUE)
createTableQuery = gsub(createTableQuery, pattern = '1-Year Geography Restrictions\r\n(with Summary Levels in Parentheses)', replace = "OneYearGeographyRestrictions", fixed = TRUE)
createTableQuery = gsub(createTableQuery, pattern = '5-Year Geography Restrictions\r\n(with Summary Levels in Parentheses)', replace = "FiveYearGeographyRestrictions", fixed = TRUE)

# create the table in SQL
SqlTools::dbSendUpdate(cn, createTableQuery)

# run bulk insert
insertStatement = paste(sep="",
                        "BULK INSERT [EDWLandingZone].[Metadata].TableCodebook",
                        " FROM '",
                        currOutputFileName,
                        "' WITH (KEEPNULLS, TABLOCK, ROWS_PER_BATCH=2000, FIRSTROW=1, FIELDTERMINATOR='/t')"
)

SqlTools::dbSendUpdate(cn, insertStatement)

indexStatement = paste(sep="",
"CREATE CLUSTERED COLUMNSTORE INDEX ccix ON Metadata.TableCodebook")

SqlTools::dbSendUpdate(cn, indexStatement)

# shrink transaction log
SqlTools::dbSendUpdate(cn, "DBCC SHRINKFILE(EDWLandingZone_log)")

# issue checkpoint
SqlTools::dbSendUpdate(cn, "CHECKPOINT")

# shrink tempdb
SqlTools::dbSendUpdate(cn, "USE tempdb")

tempFiles = DBI::dbGetQuery(cn, "
                        SELECT name FROM TempDB.sys.sysfiles
                        ")

for (i in 1:nrow(tempFiles)) {    
    currTempFileName = tempFiles[i,1]
    SqlTools::dbSendUpdate(cn, paste("DBCC SHRINKFILE(",currTempFileName,", 8)", sep=''))
}

# shutdown the database engine cleanly
SqlTools::dbSendUpdate(cn, "SHUTDOWN")