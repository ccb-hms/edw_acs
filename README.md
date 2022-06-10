<div id="top"></div>


<!-- PROJECT LOGO -->
<br />
<div align="center">

  <h3 align="center">ACS API</h3>

  <p align="center">
    A Docker containerized API-based approach to download the Census Bureau's American Community Survey 5 Year Estimates
    <br />
    <br />
    <a href="https://github.com/ccb-hms/acsAPI/issues">Report Bug</a>
    ·
    <a href="https://github.com/ccb-hms/acsAPI/issues">Request Feature</a>
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

<!-- 
  NP-TODO: Can you try to give an overview of how things are setup?  I.e., two Dockers, 
  one where SQL Server runs, another where the Python code runs, Python pulls data from 
  census.gov, writes to a shared filesystem and requests SQL Server to BULK INSERT.
  
  Maybe also some explanation of what the database looks like in terms of schema when 
  all is said and done.

  Might also be useful to point to a data dictionary on the Census site.
-->

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
If you're not familiar with Docker, you can find a tutorial [here](https://docs.docker.com/get-started/)! Experience
with Docker is not a necessarry prerequisite to running this code, but will be helpful if you would like to make modifications. 

<!-- 
  NP-TODO: explain behavior when no API key is included in invocation of the program, or
  just tell the user they have to get a key (I might slightly prefer this solution).
-->
[Request a free Census.gov API key](https://api.census.gov/data/key_signup.html)
This step is not required, but very helpful so your requests are not blocked or throttled by the Census API.

### Installation

1. Clone the repo into the directory of your choosing.
   ```sh
   git clone https://github.com/ccb-hms/acsAPI.git
   ```

2. Navigate your shell to the base directory of the newly cloned git repo.
   ```sh
   cd acsAPI
   ```

3. Build the docker image
   ```sh
   docker build -t acsapi .
   ```

4. Run the SQL Server container (for more information about Microsoft's SQL server container, view the [registry](https://hub.docker.com/_/microsoft-mssql-server)

   ```sh
   docker run \
    -e "ACCEPT_EULA=Y" \
    -e "SA_PASSWORD=Str0ngp@ssworD" \
    -p 1433:1433 \
    --name sql1 \
    --hostname sql1 \
    -v ~/Desktop/ACS_ETL:/HostData \
    -v sqldata1:/var/opt/mssql \
    -d \
    --rm \
    mcr.microsoft.com/mssql/server:2019-latest
    ```

    This command will bind mount two directories in the container: `/HostData` and `/var/opt/mssql`. `/var/opt/mssql` is the default location that SQL Server uses to store 
    database files.  By mounting a directory on your host as a data volume in your container, your database files will
    be persisted for future use even after the container is deleted.  See [here](https://docs.microsoft.com/en-us/sql/linux/sql-server-linux-docker-container-configure?view=sql-server-ver16&pivots=cs1-bash) for more details.

    `/HostData` will be used for FIXME!!!

    <!---
      NP-TODO: The old text here was a little wordy, I tried to tighten it up a little bit.
      
      Explain what the directories are used for, and / or what files end up in them.  I took a shot at the SQL 
      data directory, see what you think and write some more about the other one.  At this point (approximating a 
      naive user as best I can) I'm confused as to which directory on my host I should mount to /HostData.  Is is the root 
      of the Git repo?  A place for temp files?  Something else?   HELP!!!

      After running, it looks like /HostData ends up with intermediate files that get BULK inserted.  We might want to
      offer the user an option to clean these up as they are loaded so we don't consume a large amount of extra disk space.
    --->

    the -e option sets environment variables inside the container that are used to configure SQL Server.

5. Run the docker acsapi container
   ```sh
   docker \
    run \
        --rm \
        --name acsapi \
        -d \
        -v ~/Desktop/ACS_ETL:/HostData \
        -p 8787:8787 \
        -p 2200:22 \
        -e 'CONTAINER_USER_USERNAME=test' \
        -e 'CONTAINER_USER_PASSWORD=test' \
        acsapi 
    ```

    <!---
      NP-TODO: Try to give a little over-view of exactly what's happening here (ssh listening
      on port 22 in the container, forwarded to 2200 on host; setting up a user/password inside the container)

      We don't need TCP 8787 forwarded for this application, it is the endpoint for RStudio server.
      
      Can you explain what the mounted directory will be used for so the user 
      can decide what host directory to use?
    --->
    
 6. Run the process inside the container over SSH with your desired arguments:
    ```sh
    ssh test@localhost -p 2200 -Y -o GlobalKnownHostsFile=/dev/null -o UserKnownHostsFile=/dev/null \ python3 -u < acsAPI.py - "-y/--year [year] -k/--apikey [apikey] -u/--uid [uid] -p/--pwd [pwd] -i/--ipaddress [ipaddress] -a/--alone [alone] -s/--start [start] -z/--zcta [zcta] -st/--state [state] -c/--county [county]"
    ```

    **Available parameters are:**
    
    * **-y, --year: _str_** The year you'd like to download data for in the format "YYYY" or a range of years "YYYY-YYYY". ACS 5 year estimates are available from 2009-2020.

    * **-k, --apikey: _str_** The API key to access the Census.gov API.
    
    * **-u, --uid: _str_** The username of the SQL server you're accessing. In the example we're using the default 'sa' uid, but be sure to change this if you are using different login credentials. 

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

    * **-a, --alone: optional** Whether or not you'd like to download a single table, or all tables for the given year(s). This is helpful if you do not need all tables within a year. If _--alone_ is used, only the specified table will be pulled and exported to the mssql server. Default behavior is to download all tables available for the specified year.

    * **-z, --zcta: optional** Include this option to download all ACS 5 Year estimates by ZCTA, or Zip Code Tabulated Areas. Can be combined with the -st/--state and -c/--county options to download for multiple rollups. Default behavior downloads for zcta, state, and counties.

    * **-st, --state: optional** Include this option to download all ACS 5 Year estimates by State. Can be combined with the -z/--zcta and -c/--county options to download for multiple rollups. Default behavior downloads for zcta, state, and counties.

    * **-c, --county: optional** Include this option to download all ACS 5 Year estimates by County. Can be combined with the -st/--state and -z/--zcta options to download for multiple rollups. Default behavior downloads for zcta, state, and counties.

    * **-s, --start: _str, optional, default=‘B01001’_** The table you'd like to start with. This is usually helpful when doing a large data pull that is stopped for any reason. If the process stops due to an error, the console will print the last successful table that was pulled. If no _start_ is defined, default behavior is to start at the beginning, downloading all tables.  
<!-- 
  NP-TODO: 

  Say a few words about the SSH invocation (eg. username from acsapi docker container command)
  
  Comments about individual parameters:
      
      --alone: should the value be true / false?  not clear from comments. I specified "--alone alone"
      and got this error:
        -: error: unrecognized arguments: alone
      How do I specify a single file?  Is it the file named by --start?

      --start: let's try to be more explicit about what happens here on re-run. Does the DB get dropped
      and re-created?  Looks like maybe it does: I ran once to pull 2017 at the ZCTA level, then again 
      to pull 2019 at county level, and the 2017 ZCTA tables were gone.
  
  The code blocks under the IP address section appear to be out-dented too far.  Minor issue, but strange.

  Finally: Can you try to give the user some idea of how long they should expect the process to
  take, and what the output (if any) should look like?  We should at least let them know that 
  they will be asked to respond "yes" and enter the contianer user's password at the SSH prompt.
-->

7. Errors are written to _**logging.log**_ in the directory you bind-mounted in steps 4 and 5 with the -v option. If you prefer a csv formatted view of the logs, it's written to _**LOGFILE.csv**_ in the same aforementioned directory. 
<!-- 
  NP-TODO: Which directory, /HostData?
-->


8. When the process has finished, kill the docker containers using
  ```sh
  docker kill sql1
  docker kill acsapi
  ```
  then run the following docker command to re-initialize the db in a fresh container.
```docker run \
--name 'sql19' \
-e 'ACCEPT_EULA=Y' -e 'MSSQL_SA_PASSWORD='Str0ngp@ssworD \
-p 1433:1433 \
-v sqldata1:/var/opt/mssql \
-d mcr.microsoft.com/mssql/server:2019-latest
```
<!-- 
  NP-TODO: Code block again looks out-dented too far.
-->

9. you can view the DB with your favorite database tool by logging into SQL server. I like Azure Data Studio, but any remote-accessible db tool will work.

<!-- 
  NP-TODO: I tried running once and loading some data, which worked fine.  I then killed the container and 
  re-started, pointing at the same SQL data directory, and the SQL process seemed to hang in the re-started 
  container.  I had a similar issue with my NHANES project: 
  
  https://github.com/ccb-hms/NHANES

  Try issuing a CHECKPOINT to the DB *after* all of the tables are loaded and see if that resolves it.  Should be
  able to test manually by running the ETL process as it is now, connecting via ADS and issuing the CHECKPOINT, then
  killing / restarting the container.
-->

<p align="right">(<a href="#top">back to top</a>)</p>

<!-- CONTRIBUTING -->
## Contributing

See the [open issues](https://github.com/ccb-hms/acsAPI/issues) for a full list of proposed features (and known issues).

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

Distributed under the HMS CCB License. See `LICENSE.txt` for more information.

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- CONTACT -->
## Contact

Sam Pullman - samantha_pullman@hms.harvard.edu

<p align="right">(<a href="#top">back to top</a>)</p>


