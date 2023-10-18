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

# Create the VariableCodebook
currFileUrl = "https://api.census.gov/data/2019/acs/acs5/groups/B01001.html"
cat("reading ", currFileUrl, "\n")

df <- as.data.frame(read_html(currFileUrl) %>% html_table(fill=TRUE))
df <- df[-c(1), ]
df<-df[1:(length(df)-1)]

currOutputFileName = paste(sep = "/", outputDirectory, "VariableCodebook.csv")

#insert the table as Metadata.VariableCodebook
write.table(
     df,
     file = currOutputFileName,
     sep = "/t",
     na = "",
     row.names = FALSE,
     col.names = FALSE,
     quote = FALSE)

# generate SQL table definitions from column types in tibbles
createTableQuery = DBI::sqlCreateTable(DBI::ANSI(), paste("Metadata", "VariableCodebook", sep="."), df)

# change TEXT to VARCHAR(256)
createTableQuery = gsub(createTableQuery, pattern = "\" TEXT", replace = "\" VARCHAR(256)", fixed = TRUE)

# change DOUBLE to float
createTableQuery = gsub(createTableQuery, pattern = "\" DOUBLE", replace = "\" float", fixed = TRUE)

# remove double quotes, which interferes with the schema specification
createTableQuery = gsub(createTableQuery, pattern = '"', replace = "", fixed = TRUE)

# fix column names
createTableQuery = gsub(createTableQuery, pattern = 'Predicate.Type', replace = "PredicateType", fixed = TRUE)
createTableQuery = gsub(createTableQuery, pattern = 'Group', replace = "TableID", fixed = TRUE)

# create the table in SQL
SqlTools::dbSendUpdate(cn, createTableQuery)

# run bulk insert
insertStatement = paste(sep="",
                        "BULK INSERT [EDWLandingZone].[Metadata].VariableCodebook",
                        " FROM '",
                        currOutputFileName,
                        "' WITH (KEEPNULLS, TABLOCK, ROWS_PER_BATCH=2000, FIRSTROW=1, FIELDTERMINATOR='/t')"
)

SqlTools::dbSendUpdate(cn, insertStatement)


# Query the table codebook to get a list of all base tables
baseTables = DBI::dbGetQuery(cn, "SELECT DISTINCT(TableID)
                                    FROM [EDWLandingZone].[Metadata].[TableCodebook]
                                    WHERE DataProductType = 'Detailed Table'
                                    AND TableID like 'B%'
                                    ")


for (i in 1:nrow(baseTables)) {
    currTableName = baseTables[i,"TableID"]
    year = 2021
    #get human readable data
    codebookUrl = paste("https://api.census.gov/data/", year, "/acs/acs5/groups/", currTableName,".html", sep="")
    
    # Create the VariableCodebook
    cat("Reading ", currTableName, "codebook .\n")

    tryCatch( { 
        df <- as.data.frame(read_html(codebookUrl) %>% html_table(fill=TRUE))
        df <- df[-c(1), ]
        df<-df[1:(length(df)-1)]

        currOutputFileName = paste(sep = "/", outputDirectory, "VariableCodebook.csv")

        #insert the table as Metadata.VariableCodebook
        write.table(
            df,
            file = currOutputFileName,
            sep = "/t",
            na = "",
            row.names = FALSE,
            col.names = FALSE,
            quote = FALSE)

        # run bulk insert
        insertStatement = paste(sep="",
                                "BULK INSERT [EDWLandingZone].[Metadata].VariableCodebook",
                                " FROM '",
                                currOutputFileName,
                                "' WITH (KEEPNULLS, TABLOCK, ROWS_PER_BATCH=2000, FIRSTROW=1, FIELDTERMINATOR='/t')"
        )

        SqlTools::dbSendUpdate(cn, insertStatement)
    }, error = function(e){NA}
    )
}


updateCodebook = "UPDATE [EDWLandingZone].[Metadata].[VariableCodebook]\nSET PredicateType = REPLACE(PredicateType, 'int', 'INTEGER');\nUPDATE [EDWLandingZone].[Metadata].[VariableCodebook]\nSET PredicateType = REPLACE(PredicateType, 'STRING', 'VARCHAR(256)');\nUPDATE [EDWLandingZone].[Metadata].[VariableCodebook]\nSET PredicateType = REPLACE(PredicateType, '(not a predicate)', 'INTEGER');\nUPDATE [EDWLandingZone].[Metadata].[VariableCodebook]\nSET PredicateType = REPLACE(PredicateType, 'float', 'FLOAT');"
SqlTools::dbSendUpdate(cn, updateCodebook)

indexStatement = paste(sep="",
"CREATE CLUSTERED COLUMNSTORE INDEX ccix ON Metadata.VariableCodebook")

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