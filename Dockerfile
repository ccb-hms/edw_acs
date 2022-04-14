FROM hmsccb/analytic-workbench:version-1.3.0

# install additional python libraries
RUN pip3 install pyodbc
RUN pip3 install pandas
RUN pip3 install openpyxl
RUN pip3 install lxml
RUN pip3 install requests
RUN pip3 install io
RUN pip3 install sqlalchemy
