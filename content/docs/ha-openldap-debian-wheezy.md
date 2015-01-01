Title: HA OpenLDAP on Debian (Wheezy)
Date: 2014-12-31 00:00:00
Tags: openldap, syncrepl, ppolicy, ldaps
Category: auth
Slug: ha-openldap-debian-wheezy
Author: Fahd Sultan
Summary: A reference for configuring a Highly Available LDAP service on Debian 7, Wheezy, using openLDAP with openSSL, syncrepl, password policies, Linux-HA, and some passing references to monitoring it all.


>__A reference for configuring a Highly Available LDAP service on Debian 7, Wheezy, using openLDAP with openSSL, syncrepl, password policies, Linux-HA, and some passing references to monitoring it all.__


This doc assumes that the reader has a basic familiarity with LDAP - openLDAP specifically, openSSL, heartbeat, 
Sample files and commands are provided inline. These are almost exactly what I used and ran - with some information redacted. While links provided for references they may be stale - you are encouraged to use a search engine for updated sources.

This information is a summary of various online sources that address parts of the desired system.  Almost none of them are based on the new openLDAP configuration paradigm.  

*  [OpenLDAP Software 2.3 Administrator's Guide, "Configuring slapd", http://www.openldap.org/doc/admin23/slapdconf2.html](http://www.openldap.org/doc/admin23/slapdconf2.html)
*  [LDAP for Rocket Scientists "LDAP Configuration", http://www.zytrax.com/books/ldap/ch6/](http://www.zytrax.com/books/ldap/ch6/)

## Server setup

Launch two servers, ldap01 and ldap02
reserve an internal ip address for HA. Create a DNS entry for ldap.example.tld to this ip.  You'll configure your clients to connect to clients will connect to. c

Iptables or other firewalls

We will only allow ldaps connections so tcp/636 should be permitted. 


## Install openLDAP

Execute these steps on both the master and the slave nodes.

	//install ldap
	apt-get install ldap-utils slapd
	//gnutls-bin for debugging tls
	apt-get install gnutls-bin

#### Basic Setup

Installing the package prompts for the admin password, the domain is grabbed from the FQDN. You'll still want to setup the admin password for the cn=config RootDN.

	//locate the DN with the RootDN entry
	ldapsearch -LLL -Y EXTERNAL -H ldapi:/// -b  cn=config olcRootDN=cn=admin,cn=config dn olcRootDN olcRootPW

	//generate a password
	slappasswd -h {MD5}

#### Admin password for config db

Create an ldif file 'olcRootPW.ldif'


    dn: olcDatabase={0}config,cn=config
    changetype: modify
    add: olcRootPW
    olcRootPW: {MD5}d5heCAABBBB999G00usa==


Apply the ldif
	ldapmodify -Y EXTERNAL -H ldapi:/// -f ./olcRootPW.ldif

References:
  http://www.saruman.biz/wiki/index.php/OpenLDAP


#### Convert the old format schema 

Execute these steps on the master node. The schemata will get replicated to the slave.

Collect all schemata that you may need.

For per-host login acl include the ldapns schema include in the libpam-ldap package. [Debian Wiki, "Allowing logins on a per-host basis", http://wiki.debian.org/LDAP/PAM](http://wiki.debian.org/LDAP/PAM)

Create a file `convert_schemata.conf`

_ldapns.schema was copied from /usr/share/doc/libpam-ldap/ldapns.schema, the rest were already there._


	include /etc/ldap/schema/corba.schema
	include /etc/ldap/schema/core.schema
	include /etc/ldap/schema/cosine.schema
	include /etc/ldap/schema/duaconf.schema
	include /etc/ldap/schema/dyngroup.schema
	include /etc/ldap/schema/inetorgperson.schema
	include /etc/ldap/schema/java.schema
	include /etc/ldap/schema/misc.schema
	include /etc/ldap/schema/nis.schema
	include /etc/ldap/schema/openldap.schema
	include /etc/ldap/schema/pmi.schema
	include /etc/ldap/schema/ppolicy.schema
	include /etc/ldap/schema/ldapns.schema


_You'll probably not need them all but there are a few dependencies. ldapns.schema depends on cosine.schema so add it last._

Run `slaptest -f  convert_schema.conf -F ./ldif_output/`

If all goes well you'll find your cn=config formatted schemata in `./ldif_output/cn\=config/cn\=schema`. We will import these later. 

But first you'll need to edit them:

1. remove all line including and after 'structuralObjectClass: olcSchemaConfig'. 
2. remove the  '{NN}' from the top lines
3. add 'cn=schema,cn=config' to the 'dn' line 'dn: cn=ldapns'

My `cn\=\{12\}ldapns.ldif` file

    dn: cn=ldapns,cn=schema,cn=config
    objectClass: olcSchemaConfig
    cn: ldapns
    olcAttributeTypes: {0}( 1.3.6.1.4.1.5322.17.2.1 NAME 'authorizedService' DESC
     'IANA GSS-API authorized service name' EQUALITY caseIgnoreMatch SYNTAX 1.3.6.
     1.4.1.1466.115.121.1.15{256} )
    olcObjectClasses: {0}( 1.3.6.1.4.1.5322.17.1.1 NAME 'authorizedServiceObject'
     DESC 'Auxiliary object class for adding authorizedService attribute' SUP top
     AUXILIARY MAY authorizedService )
    olcObjectClasses: {1}( 1.3.6.1.4.1.5322.17.1.2 NAME 'hostObject' DESC 'Auxilia
     ry object class for adding host attribute' SUP top AUXILIARY MAY host )


	//add the ldapns schema
	ldapadd -f ./ldif_output/cn\=config/cn\=schema/cn\=\{12\}ldapns.ldif  -D cn=admin,cn=config -x -W


## SSL

### Generate ssl cert

I had previously setup a procedure creating and self-signing certs. A good set of instructions can be found here : [Flat Mountain, "Setting up OpenSSL to Create Certificates", http://www.flatmtn.com/article/setting-openssl-create-certificates](http://www.flatmtn.com/article/setting-openssl-create-certificates)  

Generate .pem format ssl key & cert for the heartbeat fqdn. 

	//I ran this in my ssl work dir, 
	openssl req -new -nodes -out  ldap.example.tld.req.pem -keyout private/ldap.example.tld.key.pem -days 365 -config ./openssl.cnf
	openssl ca -out ldap.example.tld.cert.pem -days 365 -config ./openssl.cnf -infiles ldap.example.tld.req.pem 

Copy the crt and key to the ldap servers into /etc/ldap/ssl - you'll have to create this directory.
	//on ldap servers
	mkdir /etc/ldap/ssl

Update the crt and key ownership and file permissions.

	//on ldap servers
	chmod 640 /etc/ldap/ssl/*
	chown root.openldap /etc/ldap/ssl/*


On ldap01 create a file 'tls.ldif'

    dn: cn=config
    add: olcTLSCACertificateFile
    olcTLSCACertificateFile: /etc/ssl/certs/exampleCA.crt
    -
    add: olcTLSCertificateFile
    olcTLSCertificateFile: /etc/ldap/ssl/ldap.example.tld.cert.pem
    -
    add: olcTLSCertificateKeyFile
    olcTLSCertificateKeyFile: /etc/ldap/ssl/ldap.example.tld.key.pem

	
Run:  `ldapmodify -f tls.ldif -D cn=admin,cn=config -x -W`

Update slapd defaults in `/etc/default/slapd`
	
	SLAPD_SERVICES="ldap://127.0.0.1:389/ ldaps:/// ldapi:///"

Restart slapd and test

	gnutls-cli-debug -p 636 127.0.0.1



## Import Schemata



## Modules

### ppolicy 

The ppolicy overlay adds more controls (password aging, reuse, timeouts, etc) over the backend database.
For more info read the man page for slapo-ppolicy

There are three steps:

* enable and configure openLDAP ppolicy module
* import ppolicy schema and overlay
* apply default policies

Create `ppolicy_module.ldif`


    dn: cn=module,cn=config
    objectClass: olcModuleList
    cn: module
    olcModulePath: /usr/lib/ldap
    olcModuleLoad: ppolicy

Create `ou_policies.ldif`


    dn: ou=policies,dc=example,dc=tld
    objectClass: top
    objectClass: organizationalUnit
    ou: policies


Create `default.policies.ldif`


    dn: cn=default,ou=policies,dc=example,dc=tld
    objectClass: top
    objectClass: device
    objectClass: pwdPolicy
    cn: default
    pwdAttribute: userPassword
    pwdMaxAge: 7776000
    pwdExpireWarning: 604800
    pwdInHistory: 13
    pwdCheckQuality: 1
    pwdMinLength: 14
    pwdMaxFailure: 5
    pwdLockout: TRUE
    pwdLockoutDuration: 1800
    pwdGraceAuthNLimit: 0
    pwdFailureCountInterval: 1800
    pwdMustChange: TRUE
    pwdAllowUserChange: TRUE
    pwdSafeModify: FALSE


Create `ppolicy_overlay.ldif`

    dn: olcOverlay=ppolicy,olcDatabase={1}hdb,cn=config
    objectClass: olcOverlayConfig
    objectClass: olcPPolicyConfig
    olcOverlay: ppolicy
    olcPPolicyDefault: cn=default,ou=policies,dc=example,dc=tld
    olcPPolicyHashCleartext: TRUE
    olcPPolicyUseLockout: TRUE


Get the schema

Add these to the running config

	ldapadd -f ppolicy_module.ldif  -D cn=admin,cn=config -x -W
	ldapadd -f ou_policies.ldif  -D cn=admin,dc=example,dc=tld -x -W

Now restart slapd,

Add the schema and db overlay.
	
	ldapadd -f ppolicy_schema.ldif  -D cn=admin,cn=config -x -W
	ldapadd -f ppolicy_overlay.ldif  -D cn=admin,cn=config -x -W
	
Add your default policies

	ldapadd -f default.policies.ldif  -D cn=admin,dc=example,dc=tld -x -W

	
Client Side Config:

	?


References:

*  [theslashroot.blogspot.com, "OpenLDAP with ppolicy", http://theslashroot.blogspot.com/2011/12/openldap-with-ppolicy.html](http://theslashroot.blogspot.com/2011/12/openldap-with-ppolicy.html)

### memberof 

_I use this for openvpn._  

Create `memberof_modules.ldif`


    dn: cn=module,cn=config
    objectClass: olcModuleList
    olcModulePath: /usr/lib/ldap
    cn: module
    olcModuleLoad: memberof


Create `memberof_overlay`


    dn: olcOverlay=memberof,olcDatabase={1}hdb,cn=config
    objectClass: olcMemberOf
    objectClass: olcOverlayConfig
    objectClass: olcConfig
    objectClass: top
    olcOverlay: memberof
    olcMemberOfDangling: ignore
    olcMemberOfRefInt: FALSE



Enable the module and add the overlay

	ldapadd -f memberof_module.ldif -D cn=admin,cn=config -x -W
	ldapadd -f memberof_overlay.ldif -D cn=admin,cn=config -x -W

Restart slapd.

### Indexes

There are instruction here : [Debian LDAP Wiki, 'Setting up an LDAP server with OpenLDAP',http://wiki.debian.org/LDAP/OpenLDAPSetup#with_cn.3Dconfig (as of July 6th, 2012 20:00 UTC)](http://wiki.debian.org/LDAP/OpenLDAPSetup#with_cn.3Dconfig)

### Replication

There are multiple replication options and strategies to consider.  Further details and information can be obtained from the Replication section of the OpenLDAP Software 2.4 Administrator's Guide and others referenced at the end of this section. 

This document will follow the most common option, a basic Syncrepl setup.  In our examples ldap01 is the _Provider_ and ldap02 is the _Consumer_.  You may be more familiar with _master/slave_ terms.  These terms have been now deprecated in OpenLDAP 2.4.

Steps: 
1. Create replication user
2. Create required indexes
3. Enable 'syncprov' overlay
4. Define Replication ACL
5. Enable Replication on 'consumer' 
 
Create a user for syncing.  use slapcat to generate the password.

`syncagent.ldif`


    dn: cn=syncagent,dc=example,dc=tld
    cn: syncagent
    objectClass: top
    objectClass: person
    sn: syncagent
    userPassword: {SSHA}SAYXXXXXXXXXXXXXXXXXXXXXXXX



Run : `ldapadd -f syncagent.ldif -D cn=admin,dc=example,dc=tld -x -W`


Add indexes `olcDbIndex2.ldif`:


    dn: olcDatabase={1}hdb,cn=config
    changetype: modify
    add: olcDbIndex
    olcDbIndex: entryUUID,entryCSN eq


Run : `ldapadd -f olcDbIndex2.ldif -D cn=admin,cn=config -x -W`



    # mostly cribbed from http://wiki.ucc.asn.au/LDAP/LazySysadmin#Single-master_with_.60cn.3Dconfig.60_replication
    version: 1

    dn: cn=config
    changetype: modify
    add: olcServerID
    olcServerID: 001 ldaps://ldap01.example.tld
    olcServerID: 002 ldaps://ldap02.example.tld

    dn: cn=module{0},cn=config
    changetype: modify
    add: olcModuleLoad
    olcModuleLoad: syncprov

    # Enable the syncprov overlay for cn=config
    dn: olcOverlay=syncprov,olcDatabase={0}config,cn=config
    changetype: add
    objectClass: olcOverlayConfig
    objectClass: olcSyncProvConfig
    olcOverlay: syncprov

    # Setup Access
    dn: olcDatabase={0}config,cn=config
    changetype: modify
    add: olcAccess
    olcAccess: to *  by dn.base="cn=syncagent,dc=example,dc=com" read  by * +0 break



Run `ldapmodify -Y EXTERNAL -H ldapi:/// -D cn=config -f ./repl_master.ldif`

On ldap02, setup config replication

Create `repl_config_slave.ldif`

    dn: olcDatabase={0}config,cn=config
    changetype: modify
    add: olcSyncrepl
    olcSyncrepl: {0}rid=1 provider=ldaps://ldap01.example.tld
     type=refreshAndPersist bindmethod=simple binddn="cn=syncagent,dc=example,dc=net" credentials=PASSWORD retry="5 5 300 5" timeout=1  tls_reqcert=never
     searchbase="cn=config"


Note: I have `tls_reqcert=never` because my certs are for ldap.example.net, which resolves to the virtual ip for HA

Run `ldapmodify -Y EXTERNAL -H ldapi:/// -D cn=config -f ./repl_conf_slave.ldif`

Setup database replication

_I could not get the next two changes to apply from one file. I tried it as two seperate files and perhaps found and fixed my typo (a line break before searchbase.  It may work for you as one file_

Create `repl_db_slave_auth.ldif`


    # Enable the syncprov overlay for olcDatabase={1}hdb,cn=config
    dn: olcOverlay=syncprov,olcDatabase={1}hdb,cn=config
    changetype: add
    objectClass: olcOverlayConfig
    objectClass: olcSyncProvConfig
    olcOverlay: syncprov
    --
    dn: olcDatabase={1}hdb,cn=config
    changetype: modify
    add: olcAccess
    olcAccess: to *  by dn.base="cn=syncagent,dc=gge,dc=brilig,dc=net" read  by * +0 break


Create `repl_db_slave_sync.ldif`


    dn: olcDatabase={1}hdb,cn=config
    changetype: modify
    add: olcSyncrepl
    olcSyncrepl: {0}rid=1 provider=ldaps://ldap01.example.tld 
     type=refreshAndPersist bindmethod=simple binddn="cn=syncagent,dc=example,dc=tld" credentials=PASSWORD retry="5 5 300 5" timeout=1  tls_reqcert=never searchbase="dc=example,dc=tld"


Run `ldapmodify -Y EXTERNAL -H ldapi:/// -D olcDatabase={1}hdb,cn=config -f ./repl_db_slave_auth.ldif`

Run `ldapmodify -Y EXTERNAL -H ldapi:/// -D olcDatabase={1}hdb,cn=config -f ./repl_db_slave_sync.ldif`

Now test your replication by creating some basic entries

On ldap01 create `ou.ldif`

    dn: ou=people,dc=example,dc=tld
    ou: people
    objectClass: organizationalUnit
    objectClass: top

    dn: ou=group,dc=example,dc=tld
    ou: group
    objectClass: organizationalUnit
    objectClass: top


Run `ldapadd -H ldap://127.0.0.1 -f ou.ldif  -D cn=admin,dc=example,dc=tld -x -W`

On ldap02:

Test with `ldapsearch -H ldap://127.0.0.1/ -x -b dc=example,dc=tld`

References:
    
*  [OpenLDAP Software 2.4 Administrator's Guide, "Replication", http://www.openldap.org/doc/admin24/replication.html](http://www.openldap.org/doc/admin24/replication.html)
*  [University Computer Club Wiki, "LDAP/LazySysadmin", http://wiki.ucc.asn.au/LDAP/LazySysadmin](http://wiki.ucc.asn.au/LDAP/LazySysadmin#Single-master_with_.60cn.3Dconfig.60_replication)
*  ["Erralt", "OpenLDAP, syncrepl via TLS/SSL", http://erralt.wordpress.com/2010/01/19/openldap-syncrepl-via-tls-ssl/](http://erralt.wordpress.com/2010/01/19/openldap-syncrepl-via-tls-ssl/)
*  [Sun Java(TM) System Directory Server 5.2 2005Q1 Deployment Planning Guide, "Chapter 6: Understanding Replication", https://docs.oracle.com/cd/E19313-01/817-7607/rep.html](https://docs.oracle.com/cd/E19313-01/817-7607/rep.html)
*  [Redhat Directory Server 8.1 Deployment Guide, "Chapter 6. Designing the Replication Process", https://access.redhat.com/documentation/en-US/Red_Hat_Directory_Server/8.1/html/Deployment_Guide/Deployment_Guide-Designing_the_Replication_Process.html#Deployment_Guide-Designing_the_Replication_Process-Introduction_to_Replication](https://access.redhat.com/documentation/en-US/Red_Hat_Directory_Server/8.1/html/Deployment_Guide/Deployment_Guide-Designing_the_Replication_Process.html#Deployment_Guide-Designing_the_Replication_Process-Introduction_to_Replication) 



## Linux-HA/heartbeat

References:

*  [Allen, Jay D., and and Cliff White. "Highly Available LDAP". Linux Journal, December 2002. http://www.linuxjournal.com/article/5505](http://www.linuxjournal.com/article/5505)


## Monitoring

### Monitoring ldap 

#### openLDAP state

*  [OpenLDAP Software 2.3 Administrator's Guide, "Monitoring", http://www.openldap.org/devel/admin/monitoringslapd.html](http://www.openldap.org/devel/admin/monitoringslapd.html)

### Monitoring syncrepl

I found a couple of post referencing a perl script and hobbit.  The original source of the script is long gone but i found the script and saved it as this [gist, "file_bb_openldap.pl", https://gist.github.com/3072089#file_bb_openldap.pl](https://gist.github.com/3072089#file_bb_openldap.pl).

#### Nagios plugin

*  [LDAP Tool Box project, "Check Syncrepl status", http://ltb-project.org/wiki/documentation/nagios-plugins/check_ldap_syncrepl_status](http://ltb-project.org/wiki/documentation/nagios-plugins/check_ldap_syncrepl_status)

### heartbeat

# Test 1

## Test 2

### Test 3

#### Test 4

##### Test 5

###### Test 6

(soon)

