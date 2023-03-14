<div id="top"></div>


<!-- PROJECT LOGO -->
<br />
<div align="center">

  <h3 align="center">American Community Survey Data Download</h3>
  <h3 align="center">A Part of the Exposome Data Warehouse Project</h3>
  <p align="center">
    A Docker containerized API-based approach to download the Census Bureau's American Community Survey 5 Year Estimates
    <br />
    <br />
    <a href="https://github.com/ccb-hms/edw_acs/issues">Report Bug</a>
    ·
    <a href="https://github.com/ccb-hms/edw_acs/issues">Request Feature</a>
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project

This project was created as a way to efficiently download large datasets from the US Census API. You can see a list of all available API's [here](https://www.census.gov/data/developers/data-sets.html). 

The American Community Survey (ACS) is an ongoing survey that provides data every year, giving communities the current information they need to plan investments and services. The ACS covers a broad range of topics about social, economic, demographic, and housing characteristics of the U.S. population. The 5-year estimates from the ACS are "period" estimates that represent data collected over a period of time. The primary advantage of using multiyear estimates is the increased statistical reliability of the data for less populated areas and small population subgroups. The 5-year estimates are available for all geographies down to the block group level. Unlike the 1-year estimates, geographies do not have to meet a particular population threshold in order to be published. 

This project creates two Docker containers, sql1 and edw_acs. The sql1 Docker container is running an intance of SQL Server. The edw_acs container is responsible for pulling the data from the census.gov site via python's requests module, writes the resulting data to a shared filesystem, then utlizes python's pyodbc module to bulk insert the data to SQL Server.

The final database structure is American Community Survey --> {year}_{geographical rollup} --> {tablename}

To further illustrate: If you are parsing multiple years from 2017-2018, and all geographical rollups, your final db schema will look like:
 
 - American Community Survey
   - 2017_COUNTY
     - B01001
     - B01002
     - B01003
   - 2017_ZCTA
     - B01001
     - B01002
     - B01003     
   - 2017_STATE
     - B01001
     - B01002
     - B01003   
   - 2018_COUNTY
     - B01001
     - B01002
     - B01003
   - 2018_ZCTA
     - B01001
     - B01002
     - B01003     
   - 2018_STATE
     - B01001
     - B01002
     - B01003


<p align="right">(<a href="#top">back to top</a>)</p>



### Built With

This project is built using the following frameworks/libraries.

* [Docker](https://Docker.com/)
* [Python](https://python.org/)
* [Pandas](https://pandas.pydata.org/) 

<p align="right">(<a href="#top">back to top</a>)</p>


<!-- GETTING STARTED -->
## Getting Started

[Ensure you have Docker installed and running on your machine.](https://docs.docker.com/get-docker/)
If you're not familiar with Docker, you can find a tutorial [here](https://docs.docker.com/get-started/). 
Experience
with Docker is not a necessarry prerequisite to running this code, but will be helpful if you would like to make modifications. 

[Request a free Census.gov API key](https://api.census.gov/data/key_signup.html)
This step is REQUIRED, so your requests are not blocked or throttled by the Census API.

**Note:** This process takes appx. 30 HOURS for all tables, all geographical rollups, across all available years. The final data is *TODO* fill in final data time here

### Installation

1. Clone the repo into the directory of your choosing.
   ```sh
   git clone https://github.com/ccb-hms/edw_acs.git
   ```

2. Navigate your shell to the base directory of the newly cloned git repo.
   ```sh
   cd edw_acs
   ```

3. Build the docker image
   ```sh
   docker build -t edw_acs .
   ```

4. Run the SQL Server container (for more information about Microsoft's SQL server container, view the [registry](https://hub.docker.com/_/microsoft-mssql-server)

   ```sh
    docker run \
    -e "ACCEPT_EULA=Y" \
    -e "SA_PASSWORD=Str0ngp@ssworD" \
    -p 1433:1433 \
    --platform linux/amd64 \
    --name sql1 \
    --hostname sql1 \
    -v C:/Users/User/EDW/edw_acs:/HostData \
    -v C:/Users/User/Desktop/sqldata1:/var/opt/mssql \
    -d \
    --rm \
    mcr.microsoft.com/mssql/server:2019-latest
    ```
    
    This also appears to work correctly with the Azure SQL Edge container by substituting `mcr.microsoft.com/azure-sql-edge:latest` for the image name.
    
    With the -d option, Docker can run your container in detached mode. This means that even if you close the terminal, the process will continue in the background. To fully stop a container, you must do so manually through Docker Desktop or the terminal via `Docker kill -container name-`.
    
    The -e option allows for the establishment of username and password variables. 
    
    The -p option is used to expose the ports that are used for the image instance.
    
    The -v option will bind mount two directories in the container: 

    `/HostData` and `/var/opt/mssql`.
    
    -`/var/opt/mssql` is the default location that SQL Server uses to store database files.  
    
    -`/HostData` is a mounted directory linking the storage of the container to your local storage. In the above example `-v C:/Users/User/EDW/edw_acs:/HostData \`, The directory on my desktop where I want my files to be saved is `C:/Users/User/EDW/edw_acs`. The `/HostData' directory is a data volume inside the container which, when data is saved to it, will now also save to your Desktop directory. 
    
    See [here](https://docs.microsoft.com/en-us/sql/linux/sql-server-linux-docker-container-configure?view=sql-server-ver16&pivots=cs1-bash) for more documentation.

5. Run the docker edw_acs container
   ```sh
  docker \
  run \
      --rm \
      --platform linux/amd64 \
      --name edw_acs \
      -d \
      -v C:\Users\User\EDW\edw_acs:/HostData \
      -p 2200:22 \
      -e 'CONTAINER_USER_USERNAME=test' \
      -e 'CONTAINER_USER_PASSWORD=test' \
      edw_acs 
    ```

    **Note**:You *MUST* use the same `-v` location for `/HostData` as in step 4. 
  
  
 6. Run the process inside the container over SSH with your desired arguments, entering 'yes' and your password ('test' if using the example above) when prompted:
    ```sh
    ssh test@localhost -p 2200 -Y -o GlobalKnownHostsFile=/dev/null -o UserKnownHostsFile=/dev/null \ python3 -u < edw_acs.py - "-y/--year [year] -k/--apikey [apikey] -u/--uid [uid] -p/--pwd [pwd] -i/--ipaddress [ipaddress] -a/--alone [alone] -s/--start [start] -z/--zcta [zcta] -st/--state [state] -c/--county [county] -b/--blockgroup [blockgroup]"
    ```

    **Available parameters are:**
    
    * **-y, --year: _str_** The year you'd like to download data for in the format "YYYY" or a range of years "YYYY-YYYY". ACS 5 year estimates are available from 2009-2020.

    * **-k, --apikey: _str_** The API key to access the Census.gov API. If you do not have one yet, [request a free Census.gov API key].(https://api.census.gov/data/key_signup.html)
    
    * **-u, --uid: _str_** The username of the SQL server you're accessing. In the example we're using the default local 'sa' uid, but be sure to change this if you are using different login credentials. 

    * **-p, --pwd: _str_** The password you defined in step 4, with the -e option.

    * **-ip, --ipaddress: _str_** The ip address that the sql1 container is using. You can find this by running the following commands in your terminal:
      ```sh
      docker network list
      ```
      to find the name of your sql1 network (usually it is 'bridge') then use:
      ```sh
      docker network inspect bridge
      ```
      to find the ip address.

    * **-a, --alone: optional** Whether or not you'd like to download a single table for the given year(s). This is helpful if you do not need all tables within a year. If _--alone_ is used, only the specified table will be pulled and exported to the mssql server. Default behavior is to download all tables available for the specified year. Use this option by including _--alone_, to not use this option simply omit _--alone_ from your SSH invocation (see example below). 

    * **-z, --zcta: optional** Include this option to download all ACS 5 Year estimates by ZCTA, or Zip Code Tabulated Areas. Can be combined with the -st/--state, -c/--county, and -b/--blockgroup options to download for multiple rollups. Default behavior downloads for zcta, state, counties, and blockgroups.

    * **-st, --state: optional** Include this option to download all ACS 5 Year estimates by State. Can be combined with the -b/--blockgroup, -c/--county, and -z/--zcta options to download for multiple rollups. Default behavior downloads for zcta, state, counties, and blockgroups.

    * **-c, --county: optional** Include this option to download all ACS 5 Year estimates by County. Can be combined with the -st/--state, -b/--blockgroup, and -z/--zcta to download for multiple rollups. Default behavior downloads for zcta, state, counties, and blockgroups.
    
    * **-b, --blockgroup: optional** Include this option to download all ACS 5 Year estimates for all states at the Block Group level. Can be combined with the -st/--state, -c/--county, and -z/--zcta options to download for multiple rollups. Default behavior downloads for zcta, state, counties, and blockgroups.

    * **-s, --start: _str, optional, default=‘B01001’_** The table you'd like to start with. This is usually helpful when doing a large data pull that is stopped for any reason. If the process stops due to an error, the console will print the last successful table that was pulled. If no _start_ is defined, default behavior is to start at B01001, the first table. 

    * **-cl, --cleanup: optional** This option will remove the downloaded files from your save directory as they are processed, freeing up space. Use this option by including _--cleanup_ in your SSH invocation.

    * **-r, --restart: optional** This option allows for restarting of a collection, without restarting the container. If your process is stopped (manually or due to an error), you can use this option to pick up where you left off. Use this option by including _--restart_ in your SSH invocation. 

    Example SSH invocation:

    ```
    ssh test@localhost -p 2200 -Y -o GlobalKnownHostsFile=/dev/null -o UserKnownHostsFile=/dev/null \ python3 -u < edw_acs.py - "--year 2020 --uid sa --pwd Str0ngp@ssworD --ipaddress 172.17.0.2 --apikey 123456789ABCDEFG --alone --start "B01001" --county --cleanup"
    ```
    
    Enter "yes" when prompted
    
    Enter "test" when prompted (or whatever password you set for your CONTAINER_USER_PASSWORD in step 5)

    This example returns county level data from 2020 just for table B01001. The breakdown of each option is below:

    * `--year 2020` : Collects data from 2020
    * `--uid sa` : Default system admin uid for mssql
    * `--pwd` Str0ngp@ssworD : This password was set up in step 4 (-e "SA_PASSWORD=Str0ngp@ssworD" )
    * `--ipaddress` 172.17.0.2 : This is the ip address the sql1 container is using
    * `--apikey` 518mAs0401rm17Mtlo987654ert : Replace this with your unique API key retrieved from the [Census.gov API key request form](https://api.census.gov/data/key_signup.html)
    * `--alone` : Only the table defined by "start" will be collected.
    * `--start` "B01001": Collect table B01001.
    * `--county` : Only the "county" geographical rollup will be collected. 
    * `--cleanup` : Do not save a local copy of each scraped table.

7. Errors are written to _**logging.log**_ in the directory you bind-mounted in steps 4 and 5 with the -v option. If you prefer a csv formatted view of the logs, it's written to _**LOGFILE.csv**_ in the `/HostData` directory you defined in steps 4 and 5. 


8. When the process has finished, kill the docker containers using
      ```sh
      docker kill sql1
      docker kill edw_acs
      ```
    then run the following docker command to re-initialize the db in a fresh container.
      ```docker run \
      --name 'sql19' \
      -e 'ACCEPT_EULA=Y' -e 'MSSQL_SA_PASSWORD='Str0ngp@ssworD \
      -p 1433:1433 \
      -v sqldata1:/var/opt/mssql \
      -d mcr.microsoft.com/mssql/server:2019-latest
      ```

9. you can view the DB with your favorite database tool by logging into SQL server. I like Azure Data Studio, but any remote-accessible db tool will work.

<p align="right">(<a href="#top">back to top</a>)</p>

<!-- CONTRIBUTING -->
## Contributing

See the [open issues](https://github.com/ccb-hms/edw_acs/issues) for a full list of proposed features (and known issues).

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#top">back to top</a>)</p>


<!-- LICENSE -->
## License

Distributed under the MIT License. See `LICENSE.txt` for more information.

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- CONTACT -->
## Contact

Sam Pullman - samantha_pullman@hms.harvard.edu

<p align="right">(<a href="#top">back to top</a>)</p>
