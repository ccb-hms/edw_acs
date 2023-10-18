
optionList = list(
  optparse::make_option(c("--container-build"), type="logical", default=FALSE, 
                        help="is this script running inside of a container build process", metavar="logical")
); 

optParser = optparse::OptionParser(option_list=optionList);
opt = optparse::parse_args(optParser);

# this variable is used below to determine how to handle errors.
# if running in a container build process, any errors encountered
# in the processing of the files should cause R to return non-zero
# status to the OS, causing the container build to fail.
runningInContainerBuild = opt[["container-build"]]

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

# use the pre-setup db
SqlTools::dbSendUpdate(cn, "USE EDWLandingZone.ACS")

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
    for (year in 2009:2022) {
        currFileUrl = paste("https://api.census.gov/data/", year, "/acs/acs5?get=NAME,group(", currTableName , ")&for=state:*&key=", sep="")

        cat("Reading ", currFileUrl, "\n")
        
        tryCatch( { 
            #get the data as a df
            df <- fromJSON(currFileUrl) %>% as.data.frame
            df <- df %>% janitor::row_to_names(row_number = 1)
            df <- subset(df, select = -NAME)
            df$YEAR <- year
            
            currOutputFileName = paste(sep = "/", outputDirectory, "currFile.csv")
            
            #if the table exists, bulk insert new data
            if (DBI::dbExistsTable(cn, currTableName) == TRUE){ 
                names(df)[names(df) == 'state'] <- 'STATE'
                
                rs <- DBI::dbGetQuery(cn, paste(sep="",
                                                "SELECT * FROM [EDWLandingZone].[ACS].",
                                                    currTableName))
                df <-df[names(rs)]
                
                #write to disk
                write.table(
                    df,
                    file = currOutputFileName,
                    sep = "/t",
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
                                    "' WITH (KEEPNULLS, TABLOCK, ROWS_PER_BATCH=2000, FIRSTROW=1, FIELDTERMINATOR='/t')"
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
                
            #if the table doesn't exist, create the schema
            }else {
                #write to disk
                write.table(
                    df,
                    file = currOutputFileName,
                    sep = "/t",
                    na = "",
                    row.names = FALSE,
                    col.names = FALSE,
                    quote = FALSE)
                
                #create schema
                createTableQuery = DBI::sqlCreateTable(DBI::ANSI(), paste("[EDWLandingZone].[ACS]",currTableName, sep="."), df)

                #edit schema to fit variablecodebook                
                createTableQuery = gsub(createTableQuery, pattern = "\" TEXT", replace = "\" VARCHAR(256)", fixed = TRUE)
                createTableQuery = gsub(createTableQuery, pattern = "E\" VARCHAR(256)", replace = "E\" INTEGER", fixed = TRUE)
                createTableQuery = gsub(createTableQuery, pattern = "M\" VARCHAR(256)", replace = "M\" INTEGER", fixed = TRUE)
                createTableQuery = gsub(createTableQuery, pattern = "NAME\" INTEGER", replace = "NAME\" VARCHAR(256)", fixed = TRUE)
                createTableQuery = gsub(createTableQuery, pattern = "YEAR\" INT", replace = "YEAR\" INTEGER", fixed = TRUE)
                
                # remove double quotes, which interferes with the schema specification
                createTableQuery = gsub(createTableQuery, pattern = '"', replace = "", fixed = TRUE)

                #create table
                SqlTools::dbSendUpdate(cn, createTableQuery)
                
                #bulk insert the data
                insertStatement = paste(sep="",
                                    "BULK INSERT [EDWLandingZone].[ACS].",
                                    currTableName,
                                    " FROM '",
                                    currOutputFileName,
                                    "' WITH (KEEPNULLS, TABLOCK, ROWS_PER_BATCH=2000, FIRSTROW=1, FIELDTERMINATOR='/t')"
                )
                
                SqlTools::dbSendUpdate(cn, insertStatement)
                
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
