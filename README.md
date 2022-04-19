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

<p align="right">(<a href="#top">back to top</a>)</p>



### Built With

This project is built using the following frameworks/libraries.

* [Docker](https://Docker.com/)
* [Python](https://python.org/)
* [Pandas](https://pandas.pydata.org/) 

<p align="right">(<a href="#top">back to top</a>)</p>


<!-- GETTING STARTED -->
## Getting Started

[Request a free Census.gov API key](https://api.census.gov/data/key_signup.html)
This step is not required, but very helpful so your requests are not blocked or throttled by the Census API.

### Installation

1. Clone the repo into the directory of your choosing.
   ```sh
   git clone https://github.com/ccb-hms/acsAPI.git
   ```

3. Build the docker image
   ```sh
   docker build -t acsapi .
   ```
4. run the docker sql1 container
   ```sh
   docker run \
    -e "ACCEPT_EULA=Y" \
    -e "SA_PASSWORD=<YourStrong@Passw0rd>" \
    -p 1433:1433 \
    --name sql1 \
    --hostname sql1 \
    -v ~/Desktop/ACS_ETL:/HostData \
    -d \
    --rm \
    mcr.microsoft.com/mssql/server:2019-latest
    ```

5. run the docker acsapi container
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
    
 6. SSH into the acsapi container, and run the process with your desired arguments:
    ```sh
    ssh test@localhost -p 2200 -Y -o GlobalKnownHostsFile=/dev/null -o UserKnownHostsFile=/dev/null python3 -u < acsAPI.py - [year] [start] [multi]
    ```
    
    **Available parameters are:**
    
    * **year: _str_** The year you'd like to download data for in the format "YYYY" or a range of years "YYYY-YYYY". ACS 5 year estimates are available from 2009-2020.
    
    * **start: _str, optional, default=‘B01001’_** The table you'd like to start with. This is usually helpful when doing a large data pull that is stopped for any reason. If the process stops due to an error, the console will print the last successful table that was pulled. If no _start_ is defined, default behavior is to start at the beginning, downloading all tables.  
    
    * **multi: _bool, optional, default=True_** Whether or not you'd like to download a single table, or all tables for the given year. This is helpful if you do not need all tables within a year. If multi=False, only the specified table will be pulled and exported to the mssql server. Default behavior is multi=True, downloading all tables available for the specified year.

7. Errors are written to _**failed_get_acs_data.txt**_ (lists errors encountered during the initial pulling of data) and **_failed_sql.txt_** (lists errors that occurred during the SQL ETL process.)

8.When the process has finished, kill the docker containers.
  ```sh
  docker kill sql1
  docker kill workbench 
  ```
  
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


