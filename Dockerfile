FROM hmsccb/analytic-workbench:version-1.3.0

# install additional python libraries
RUN pip3 install pyodbc==4.0.32
RUN pip3 install pandas==1.4.2
RUN pip3 install openpyxl==3.0.9
RUN pip3 install lxml==4.8.0
RUN pip3 install requests==2.27.1
RUN pip3 install sqlalchemy==1.4.35
