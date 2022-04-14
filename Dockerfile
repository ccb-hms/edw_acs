#
# Data Science Workbench Image
#

FROM mcr.microsoft.com/mssql/server:2019-CU12-ubuntu-20.04

#------------------------------------------------------------------------------
# Basic initial system configuration
#------------------------------------------------------------------------------

USER root

# install standard Ubuntu Server packages
RUN yes | unminimize

# we're going to create a non-root user at runtime and give the user sudo
RUN apt-get update && \
	apt-get -y install sudo \
	&& echo "Set disable_coredump false" >> /etc/sudo.conf
	
# set locale info
RUN echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen \
	&& apt-get update && apt-get install -y locales \
	&& locale-gen en_US.utf8 \
	&& /usr/sbin/update-locale LANG=en_US.UTF-8
ENV LC_ALL en_US.UTF-8
ENV LANG en_US.UTF-8
ENV TZ=America/New_York

WORKDIR /tmp

#------------------------------------------------------------------------------
# Install system tools and libraries via apt
#------------------------------------------------------------------------------

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
	&& apt-get install \
		-y \
		#--no-install-recommends \
		ca-certificates \
		curl \
		less \
		libgomp1 \
		libpango-1.0-0 \
		libxt6 \
		libsm6 \
		make \
		texinfo \
		libtiff-dev \
		libpng-dev \
		libicu-dev \
		libpcre3 \
		libpcre3-dev \
		libbz2-dev \
		liblzma-dev \
		gcc \
		g++ \
		openjdk-8-jre \
		openjdk-8-jdk \
		gfortran \
		libreadline-dev \
		libx11-dev \
		libcurl4-openssl-dev \ 
		libssl-dev \
		libxml2-dev \
		wget \
		libtinfo5 \
		openssh-server \
		ssh \
		xterm \
		xauth \
		screen \
		tmux \
		git \
		libgit2-dev \
		nano \
		emacs \
		vim \
		man-db \
		zsh \
		unixodbc \
		unixodbc-dev \
		gnupg \
		krb5-user \
		python3-dev \
		python3 \ 
		python3-pip \
		alien \
		libaio1 \
		pkg-config \ 
		libkrb5-dev \
		unzip \
		cifs-utils \
	&& rm -rf /var/lib/apt/lists/*


#------------------------------------------------------------------------------
# Configure system tools
#------------------------------------------------------------------------------

# required for ssh and sshd	
RUN mkdir /var/run/sshd	

# configure X11
RUN sed -i "s/^.*X11Forwarding.*$/X11Forwarding yes/" /etc/ssh/sshd_config \
    && sed -i "s/^.*X11UseLocalhost.*$/X11UseLocalhost no/" /etc/ssh/sshd_config \
    && grep "^X11UseLocalhost" /etc/ssh/sshd_config || echo "X11UseLocalhost no" >> /etc/ssh/sshd_config	

# tell git to use the cache credential helper and set a 1 day-expiration
RUN git config --system credential.helper 'cache --timeout 86400'


#------------------------------------------------------------------------------
# Install and configure database connectivity components
#------------------------------------------------------------------------------

# install MS SQL Server ODBC driver
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
	&& echo "deb [arch=amd64] https://packages.microsoft.com/ubuntu/18.04/prod bionic main" | tee /etc/apt/sources.list.d/mssql-release.list \
	&& apt-get update \
	&& ACCEPT_EULA=Y apt-get install msodbcsql17

# install FreeTDS driver
WORKDIR /tmp
RUN wget ftp://ftp.freetds.org/pub/freetds/stable/freetds-1.1.40.tar.gz
RUN tar zxvf freetds-1.1.40.tar.gz
RUN cd freetds-1.1.40 && ./configure --enable-krb5 && make && make install
RUN rm -r /tmp/freetds*

# tell unixodbc where to find the FreeTDS driver shared object
RUN echo '\n\
[FreeTDS]\n\
Driver = /usr/local/lib/libtdsodbc.so \n\
' >> /etc/odbcinst.ini

# install Oracle Instant Client and Oracle ODBC driver 
ARG ORACLE_RELEASE=18
ARG ORACLE_UPDATE=5
ARG ORACLE_RESERVED=3

RUN wget https://download.oracle.com/otn_software/linux/instantclient/${ORACLE_RELEASE}${ORACLE_UPDATE}000/oracle-instantclient${ORACLE_RELEASE}.${ORACLE_UPDATE}-basic-${ORACLE_RELEASE}.${ORACLE_UPDATE}.0.0.0-${ORACLE_RESERVED}.x86_64.rpm \
    && wget https://download.oracle.com/otn_software/linux/instantclient/${ORACLE_RELEASE}${ORACLE_UPDATE}000/oracle-instantclient${ORACLE_RELEASE}.${ORACLE_UPDATE}-devel-${ORACLE_RELEASE}.${ORACLE_UPDATE}.0.0.0-${ORACLE_RESERVED}.x86_64.rpm \
    && wget https://download.oracle.com/otn_software/linux/instantclient/${ORACLE_RELEASE}${ORACLE_UPDATE}000/oracle-instantclient${ORACLE_RELEASE}.${ORACLE_UPDATE}-sqlplus-${ORACLE_RELEASE}.${ORACLE_UPDATE}.0.0.0-${ORACLE_RESERVED}.x86_64.rpm \
    && wget https://download.oracle.com/otn_software/linux/instantclient/${ORACLE_RELEASE}${ORACLE_UPDATE}000/oracle-instantclient${ORACLE_RELEASE}.${ORACLE_UPDATE}-odbc-${ORACLE_RELEASE}.${ORACLE_UPDATE}.0.0.0-${ORACLE_RESERVED}.x86_64.rpm

RUN alien -i oracle-instantclient${ORACLE_RELEASE}.${ORACLE_UPDATE}-basic-${ORACLE_RELEASE}.${ORACLE_UPDATE}.0.0.0-${ORACLE_RESERVED}.x86_64.rpm \
   && alien -i oracle-instantclient${ORACLE_RELEASE}.${ORACLE_UPDATE}-devel-${ORACLE_RELEASE}.${ORACLE_UPDATE}.0.0.0-${ORACLE_RESERVED}.x86_64.rpm \
   && alien -i oracle-instantclient${ORACLE_RELEASE}.${ORACLE_UPDATE}-sqlplus-${ORACLE_RELEASE}.${ORACLE_UPDATE}.0.0.0-${ORACLE_RESERVED}.x86_64.rpm \
   && alien -i oracle-instantclient${ORACLE_RELEASE}.${ORACLE_UPDATE}-odbc-${ORACLE_RELEASE}.${ORACLE_UPDATE}.0.0.0-${ORACLE_RESERVED}.x86_64.rpm

RUN rm oracle-instantclient*.rpm 

# define the environment variables for oracle
ENV LD_LIBRARY_PATH=/usr/lib/oracle/${ORACLE_RELEASE}.${ORACLE_UPDATE}/client64/lib/${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH} \
    ORACLE_HOME=/usr/lib/oracle/${ORACLE_RELEASE}.${ORACLE_UPDATE}/client64 \
    PATH=$PATH:$ORACLE_HOME/bin

RUN echo "/usr/lib/oracle/${ORACLE_RELEASE}.${ORACLE_UPDATE}/client64/lib" | sudo tee /etc/ld.so.conf.d/oracle.conf

# tell unixodbc where to find the Oracle driver shared object
RUN echo '\n\
[Oracle]\n\
Driver = /usr/lib/oracle/'${ORACLE_RELEASE}'.'${ORACLE_UPDATE}'/client64/lib/libsqora.so.18.1 \n\
' >> /etc/odbcinst.ini

# install pyodbc
RUN pip3 install pyodbc
RUN pip3 install pandas
RUN pip3 install openpyxl
RUN pip3 install lxml

#------------------------------------------------------------------------------
# Final odds and ends
#------------------------------------------------------------------------------

# Copy startup script
RUN mkdir /startup
COPY startup.sh /startup/startup.sh
RUN chmod 700 /startup/startup.sh

# Create a mount point for host filesystem data
RUN mkdir /HostData

# Set default kerberos configuration
COPY krb5.conf /etc/krb5.conf

CMD ["/startup/startup.sh"]
