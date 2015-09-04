#!/usr/bin/env python
#
#
#
# Name: order_monitoring.py
#
# Description: 
#
# Author: Adam Dosch
#
# Date: 08-07-2013
#
##########################################################################################
# Change        Date            Author              Description
##########################################################################################
#  001          08-07-2013      Adam Dosch          Initial release
#  002          08-16-2013      Adam Dosch          Making a shitload of improvments to
#                                                   have this reporting tool functional by
#                                                   creating an OrderStatusReport class,
#                                                   getting HTML e-mail formatting worked
#                                                   out, etc.
#  003          08-19-2013      Adam Dosch          Added 'orderstats' section information
#                                                   and adding '-m' and '-d' flag logic
#  004          08-20-2013      Adam Dosch          Changed 'orderstats' to 'orderinfo' so
#                                                   it was a bit more generic on naming.
#                                                   Fixing '-e' logic by making email_to
#                                                   a globally accessible variable.
#                                                   Making '-d' a visible option instead
#                                                   of a hidden one.
#                                                   Fixing orderinfo query for completed,
#                                                   partial and submitted orders to use
#                                                   todays_date generated by datetime, and
#                                                   also changed verbage to include the
#                                                   word "Todays" behind the names as well
#                                                   Added '-n' option to break out runtime
#                                                   informatoin separately from order info
#  005          08-21-2013      Adam Dosch          Adding '__author__' references
#  006          08-22-2013      Adam Dosch          Had a typo for today's ordered orders
#                                                   verbage.
#  007		07-23-2014	Adam Dosch	    Updating notifications
#  008          03-31-2015	Adam Dosch	    Updating notification addresses
#
##########################################################################################
#
#
# To add a new reporting section:
#
# 1) Add a new argparse parameter to toggle it on
#
# 2) Add if logic in main() to process parameter and setup OrderInfo object
#
# 3) Add value onto 'types' list in OrderInfo class
#
# 4) Add query and/or result set in getResults() method in OrderInfo class
#
# 5) Add section layouts and any customization in createReportSection() method in OrderStatusReport class
#

__author__ = "Adam Dosch"

import os
import sys
import datetime
import itertools
import re
import argparse
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import platform

import psycopg2

verbose = False

# E-mail Recipients/Subject
email_from = 'espa@espa.cr.usgs.gov'

global email_to
email_to = ['cbturner@usgs.gov', 'gschmidt@usgs.gov','dhill@usgs.gov','rdilley@usgs.gov']

email_subject = "ESPA Order Monitoring - " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

#-------------------------------
# Class:  OrderReport
#-------------------------------

class OrderStatusReport(object):
    
    def __init__(self):
        self.finalReport = ""
        
        self.reportTitle = "ESPA Order Status"
        
        # Append initial head + body of report
        self.finalReport += self._generateReportHeader()
        
        # Row color iterator
        self.row_color_style = itertools.cycle(["""background-color:#ffffff;""", """background-color:#e9ecf5;"""])

        # Set today's date in YYYY-MM-DD format to reference
        self.todays_date = datetime.datetime.now().strftime("%Y-%m-%d")
    
    def createReportSection(self, monitorType, reportData):
        """
        Will generate a report section for a selected reporting section
        in HTML and append it to overall report body
        """
        
        # Section Heading/Title/URL layout
        sectionLayouts = {
            'failedscenes': "Failed Scenes",
            'failedscenes_headings': ['Order Date','Internal OID', 'ESPA OID', 'Order Source', 'Failed'],
            'failedscenes_url': "https://espa.cr.usgs.gov/admin/ordering/",
            'failedscenes_espastatus': 'error',
            'failedscenes_titleurl': "https://espa.cr.usgs.gov/admin/ordering/scene/?status__exact=error", # Don't use this yet, but could hyper-link title if we wanted
            
            'onorderscenes': "On-Order Scenes",
            'onorderscenes_headings': ['Order Date','Internal OID', 'ESPA OID', 'Order Source', 'On Order'],
            'onorderscenes_url': "https://espa.cr.usgs.gov/admin/ordering/",
            'onorderscenes_espastatus': 'onorder',
            'onorderscenes_titleurl': "https://espa.cr.usgs.gov/admin/ordering/scene/?status__exact=onorder", # Don't use this yet, but could hyper-link title if we wanted
                
            'unavailablescenes': "Unavailable Scenes",
            'unavailablescenes_headings': ['Order Date', 'Internal OID', 'ESPA OID', 'Order Source', 'Unavailable', 'Note'],
            'unavailablescenes_url': "https://espa.cr.usgs.gov/admin/ordering/",
            'unavailablescenes_espastatus': 'unavailable',
            'unavailablescenes_titleurl': "https://espa.cr.usgs.gov/admin/ordering/scene/?status__exact=unavailable", # Don't use this yet, but could hyper-link title if we wanted
            
            'orderinfo': "Order Information",
            'orderinfo_headings': [],
            'orderinfo_url': '',
            'orderinfo_espastatus': '',
            'orderinfo_titleurl': "https://espa.cr.usgs.gov/admin/", # Don't use this yet, but could hyper-link title if we wanted

            'runtimeinfo': "Runtime Information",
            'runtimeinfo_headings': [],
            'runtimeinfo_url': '',
            'runtimeinfo_espastatus': '',
            'runtimeinfo_titleurl': "https://espa.cr.usgs.gov/admin/" # Don't use this yet, but could hyper-link title if we wanted
        }
        
        # Get record count for section
        recCount = len(reportData)
        
        # If no results for particular section, lets create one row with whitespace in all columns for asthetic's sake
        if recCount == 0:
            row = ()
            
            for col in sectionLayouts[monitorType + "_headings"]:
                row = row + (' ',)
            
            reportData = reportData + (row,)
        
        # Create table and title for passed in section
        # - if orderinfo or runtimeinfo, don't include record Count -- sure there's a more elegant way to do this
        if monitorType in ['orderinfo', 'runtimeinfo']:
            section = """<table border=1 style="font-size:12px;color:#3a657a;border-width:1px;width:80%%;border-color:#729ea5;border-collapse:collapse;"><tr style="background-color:#dcdcdc;border-width:0px;"><th style="font-size:16px;background-color:#3a657a;border-width:1px;padding:8px;border-style:solid;border-color:#729ea5;text-align:left;color:#e8e683;font-weight:bold;">%s </th></tr>""" % (sectionLayouts[monitorType])
        else:
                        section = """<table border=1 style="font-size:12px;color:#3a657a;border-width:1px;width:80%%;border-color:#729ea5;border-collapse:collapse;"><tr style="background-color:#dcdcdc;border-width:0px;"><th style="font-size:16px;background-color:#3a657a;border-width:1px;padding:8px;border-style:solid;border-color:#729ea5;text-align:left;color:#e8e683;font-weight:bold;">%s (%s)</th></tr>""" % (sectionLayouts[monitorType], recCount)
        # Lets generate section table headings
        section += """<tr style="background-color:#dcdcdc;">"""
        
        for heading in sectionLayouts[monitorType + '_headings']:
            section += """<th style="font-size:14px;background-color:#f1f1f1;border-width: 1px;padding: 8px;border-style: solid;border-color: #3a657a;text-align:left;">%s</th>""" % (heading)
        
        section += """</tr>"""
        
        # Initialize row counter
        ctr = 0
        
        # Lets generate table row+data content
        for row in reportData:
            # Incrementing row counter
            ctr += 1
            
            # Building table row for section
            section += """<tr style="%s">""" % next(self.row_color_style)
            section += "\n\n\n\n"
            
            # Our ESPA order ID is 'always' ordinal position 2, so we're going to put in a URL hot-link
            for i in range(0, len(row), 1):
                
                # If oid column, store oid
                if i == 1:
                    oid = row[i]
                
                # If espa-oid column, store it and create hyper-linked URL and break out
                if i == 2:
                    espa_oid = row[i]
                    
                    url = """<a href="%s/order/%s">%s</a>""" % (sectionLayouts[monitorType + "_url"], oid, row[i])
                    section += """<td style="font-size:12px;border-width: 1px;padding: 8px;border-style: solid;border-color: #3a657a;">%s</td>\n""" % url
                    continue

                # if number for errors, onorder or unavailable, create hyper-linked URL and break out
                if i == 4:
                    url = """<a href="%s/scene/?q=%s&status__exact=%s">%s</a>""" % (sectionLayouts[monitorType + "_url"], espa_oid, sectionLayouts[monitorType + "_espastatus"], row[i])
                    section += """<td style="font-size:12px;border-width: 1px;padding: 8px;border-style: solid;border-color: #3a657a;">%s</td>\n""" % url
                    continue
                # This is for everything else not hyper-linked
                else:
                    
                    # if orderdate column, '-m' is set, and date is within today's date, lets italicize it
                    if args.marktodaysorders == True and i == 0 and re.search(self.todays_date, str(row[i])):
                        section += """<td style="font-size:12px;border-width: 1px;padding: 8px;border-style: solid;border-color: #3a657a;color: #0C1418">%s</td>""" % row[i]
                    else:
                        section += """<td style="font-size:12px;border-width: 1px;padding: 8px;border-style: solid;border-color: #3a657a;">%s</td>""" % row[i]
            
            # Wrap up up table row with termination tag
            section += "</tr>"
            
            # if '-d' is set, then lets enforce record display limit in e-mail, and break out of the loop
            if type(args.displaylimit) is list:
                if ctr == args.displaylimit[0]:
                    break
        
        # Finishing of table for passed in section
        section += "</table><br>"
        
        # Hack --- for whatever reason HTML issues bigtime in G-mail when all the markup language is globbed up.
        # even though it's properly tagged and terminated.  Went through every line of HTML and found no issues.
        # The newlines between sections fixed the issue.
        section += "\n\n\n\n"
        
        # Appending it to over-all report
        self.finalReport += section
        
    def _generateReportHeader(self):
        return """
        <html>
            <head>
                <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
                <title>%s</title>
            </head>
        
        <body>
        """ % (self.reportTitle)

    def _generateReportFooter(self):
        """
        Generate the last part of the HTML report for e-mailing
        """
        
        self.finalReport += """<br></body></html>"""
    
    def finalizeReport(self):
        """
        Perform last preparations for Order Status report prior to e-mailing
        """
        
        self._generateReportFooter()

#-------------------------------
# Class:  OrderInfo
#-------------------------------
  
class OrderInfo(object):
    """
    OrderInfo class is a object set up to check, query and gather for a specific
    type of ordering issue with ESPA processing framework, specifically on-demand orders.
    monitorTypes: failedscenes, unavailablescenes, onorderscenes, orderinfo
    """
    
    def __init__(self, monitorType):
        
        # Order monitoring types
        types = ['failedscenes', 'unavailablescenes', 'onorderscenes', 'orderinfo', 'runtimeinfo']
        
        # DB credential dict initialization
        self.creds = {}
        
        # Does the passed in monitorType match anything we support?
        if monitorType in types:
            self.monitorType = monitorType
        else:
            raise Exception("Unsupported passed in monitorType for OrderInfo()")

        # Set today's date in YYYY-MM-DD format to reference
        self.todays_date = datetime.datetime.now().strftime("%Y-%m-%d")

        # Determine ESPA Admin URL base
        # - derived off of what user we are running this script as, defaults to espa-dev
        if os.environ['USER'] == "espa":
            self.urlBase = "https://%s.cr.usgs.gov/admin" % os.environ['USER']
        else:
            self.urlBase = "https://espa-dev.cr.usgs.gov/admin"

        # Get homedir location of user running this to look for db creds
        if os.environ.has_key('HOME'):
            credLocation = os.environ['HOME']
        else:
            # Defaulting to 'something' vs exception out --- stupid, but whatever
            credLocation = "/tmp"
        
        # Try and fetch DB credentials
        if not self._getDBCreds(credLocation):
            raise Exception("Problem fetching or getting database credentials!")

        # Create DB connetion
        self.db_conn = self._connect_db(host=self.creds["h"], user=self.creds["u"], password=self.creds["p"], db=self.creds["d"])
    
        if not self.db_conn:
            raise Exception("Cound not establish connection to the DB on %s!  Either the username, password or database options are muffed or you're locked out." % (platform.node()))

    def __exit__(self):
        # any object destructor shit goes here
        self.db_conn.close()
        
    def _getDBCreds(self, credLocation):
        """
        Get DB credentials from db creds file
        """
        # Lets check and see if our dbcreds file exists?
        # This is where we will know what DB environment to update
        credFile = "%s/.dbnfo" % credLocation
        
        if os.path.isfile(credFile):
            try:
                # open and read data from creds file
                f = open(credFile, "r")
            
                data = f.readlines()
                
                f.close()
                
            except Exception:
                return False
            
            # stuff creds in a dict
            for line in data:
                if len(line) > 0 and "=" in line:
                    (k, v) = line.split("=")
                    self.creds[k] = v.strip("\n")    
            return True
        else:
            return False
    
    def _connect_db(self, host, user, password, db, port=3306):
        """
        Connect to database
        """
        try:
            return psycopg2.connect(host=host, port=port, user=user, passwd=password, db=db)
        except psycopg2.Error:
            print "Could not connect to postgres database"
            
        return False

    def getResults(self):
        """
        Get results of specified monitorType specificed on instantiation
        """
        # Initialize rows tuple
        rows = tuple()
        
        # Set hitDB flag to false
        hitDB = False
        
        # Limit queries to so many records (to control table lengths in e-mail in case we have a shit-ton of issues)
        if args.recordlimit:
            recordlimit = "limit " + str(args.recordlimit[0])
        # Default is to show everything but we could hard-code a limit here
        else:
            recordlimit = ""
        
        # Create DB cursor
        cursor = self.db_conn.cursor()
        
        # Match monitorType and do set proper query
        if self.monitorType == "failedscenes":
            sql = "select ordering_order.order_date, ordering_order.id, ordering_order.orderid, ordering_order.order_source, count(ordering_scene.name) as error_scenes from ordering_scene left join ordering_order on ( ordering_order.id = ordering_scene.order_id ) where ordering_scene.status = 'Error' group by ordering_order.order_date desc " + recordlimit + ";"
            hitDB = True
        
        if self.monitorType == "unavailablescenes":
            sql = "select ordering_order.order_date, ordering_order.id, ordering_order.orderid, ordering_order.order_source, count(ordering_scene.name) as unavail_scenes, ordering_scene.note from ordering_scene left join ordering_order on ( ordering_order.id = ordering_scene.order_id ) where ordering_scene.status = 'unavailable' group by ordering_order.order_date desc " + recordlimit + ";"
            hitDB = True
        
        if self.monitorType == "onorderscenes":
            sql = "select ordering_order.order_date, ordering_order.id, ordering_order.orderid, ordering_order.order_source, count(ordering_scene.name) as onorder_scenes from ordering_scene left join ordering_order on ( ordering_order.id = ordering_scene.order_id ) where ordering_scene.status = 'onorder' group by ordering_order.order_date desc " + recordlimit + ";"
            hitDB = True
        
        if self.monitorType == "orderinfo":
            rows = tuple()
            
            # Order state counts
            sql = """select "<b>Today's Total Orders(s)</b>", count(orderid) from ordering_order where order_date between '%s 00:00:00' and '%s 23:59:59' union all select "<b>Today's Partial Order(s)</b>", count(orderid) from ordering_order where order_date between '%s 00:00:00' and '%s 23:59:59' and status = 'partial' union all select "<b>Today's Completed Order(s)</b>", count(orderid) from ordering_order where order_date between '%s 00:00:00' and '%s 23:59:59' and status = 'complete' union all select "<b>Today's Ordered Order(s)</b>", count(orderid) from ordering_order where order_date between '%s 00:00:00' and '%s 23:59:59' and status = 'ordered'""" % (self.todays_date, self.todays_date, self.todays_date, self.todays_date, self.todays_date, self.todays_date, self.todays_date, self.todays_date)
            hitDB = True

            
        if self.monitorType == "runtimeinfo":
            rows = tuple()
            
            # Host
            row = ('<b>Host Generated From: </b>', platform.node())
            rows = rows + (row,)
            
            # Record limit
            row = ('<b>Record Limit: </b>',)
            
            if type(args.recordlimit) == list:
                row = row + (args.recordlimit[0],)
            else:
                row = row + ("none",)
            
            rows = rows + (row,)
            
            # Display limit
            row = ('<b>Display Limit: </b>',)
            
            if type(args.displaylimit) == list:
                row = row + (args.displaylimit[0],)
            else:
                row = row + ("none",)
            
            rows = rows + (row,)
            
            # Mark Today's Order option
            row = ('<b>Todays Orders Indicator</b>',)
            
            row = row + (str(args.marktodaysorders),)
            
            rows = rows + (row,)
            
        # Let's fetch the DB data and return it
        if hitDB:
            
            try:
                cursor.execute(sql)
                    
                rows = rows + cursor.fetchall()
            
            except Exception, e:
                print "Exception: ", e
                sys.exit(1)
        
        # Return the results (some types won't need to hit the DB to provide results)
        return rows

def send_email(sender, recipients, subject, body):
    """
    Send out an e-mail to recipient(s)
    """
 
    # Create message container - the correct MIME type is multipart/alternative here!
    msg = MIMEMultipart('alternative')
    msg['subject'] = subject
    msg['From'] = sender
    msg['To'] = ""
    
    # Have to add to proper To recipient header for each e-mail recipient
    for addr in recipients:
        msg.add_header('To', addr)

    msg.preamble = "Your mail reader does not support the following HTML report format.  Lame."
 
    # Record the MIME type text/html.
    html_body = MIMEText(body, 'html')
 
    # Attach parts into message container.
    # According to RFC 2046, the last part of a multipart message, in this case
    # the HTML message, is best and preferred.
    msg.attach(html_body)
 
    ### DEBUGGING SMTP handshake only
    #server.set_debuglevel(1)
 
    # The actual sending of the e-mail
    server = smtplib.SMTP('localhost')
    
    # use this if you have multiple recipients generated via list
    server.sendmail(sender, msg.get_all('To'), msg.as_string())
    
    # use this if you're using a non-list (string) for e-mail recipient
    #server.sendmail(FROM, [TO], msg.as_string())
    
    # Close smtp connection
    server.quit()

#=========================================================================================================
#               START OF SCRIPT --- DO NOT EDIT BELOW UNLESS YOU KNOW WHAT YOU ARE DOING
#=========================================================================================================

def main():
    # globals
    global email_to
    
    #Set up option handling
    parser = argparse.ArgumentParser(description="This is a script that should be ran on a regularly scheduled basis to monitor on-demand order/scene statuses for ESPA.  There are some hidden options: -v, -r, and -d.  '-v' controls verbose-ness (for debugging).  '-r' controls limit of how many records for each report to return overall.  '-d' controls the limit of the overall results to display in the e-mail (to keep e-mail more brief)")
    
    # Visible options
    parser.add_argument("-f", "--failed-scenes", action="store_true", dest="failedscenes", help="Report on any failed scenes for orders within ESPA")
    parser.add_argument("-u", "--unavailable-scenes", action="store_true", dest="unavailablescenes", help="Report on any unavailable scenes for orders within ESPA")
    parser.add_argument("-o", "--onorder-scenes", action="store_true", dest="onorderscenes", help="Username to changed credentials for (e.g. [espa|esapdev] )")
    parser.add_argument("-s", "--order-info", action="store_true", dest="orderinfo", help="Provide overall statistics for submitted orders on queried interval")
    parser.add_argument("-e", "--email-to-override", type=str, action="store", dest="email_to_override", nargs=1, help="Override default e-mail-to address.  Useful for testing or one-off report running.")
    parser.add_argument("-m", "--mark-todays-orders", action="store_true", dest="marktodaysorders", default=False, help="Will italicize the current day order's order date field to visually pick it out for analysis")
    parser.add_argument("-d", "--display-limit", type=int, action='store', nargs=1, dest="displaylimit", default=False, help="Controls how many of the overall results for each section to display in the e-mail table.  Helps with size and length of e-mail report.")
    parser.add_argument("-n", "--runtime-info", action='store_true', dest="runtimeinfo", help="Report on the runtime script configuration.")
    
    # Hidden options not on help output
    parser.add_argument("-r", "--record-limit", type=int, action='store', nargs=1, dest="recordlimit", default=False, help=argparse.SUPPRESS)

    parser.add_argument("-v", "--verbose", action='store_true', dest="verbose", default=False, help=argparse.SUPPRESS)
    
    # Option isn't implemented yet, so we're hiding for now -- TODO
    #parser.add_argument("-i", "--query-interval", action="store", dest="queryinterval", default="4h", help="Define interval to query data for reporting information.  Format must be <n><i> where <n> is an integer value, and <i> is an abbreviated interval of time, h=hours, d=days, m=minutes")
    parser.add_argument("-i", "--query-interval", action="store", dest="queryinterval", default="4h", help=argparse.SUPPRESS)
    
    
    # Parse those options!
    global args
    args = parser.parse_args()
    
    # If nothing is passed, print argparse help at a minimum
    if len(sys.argv) - 1 == 0:
        parser.print_help()
        sys.exit(1)
    
    # Any e-mail-to overriding set?
    if type(args.email_to_override) == list:
        # Should really reg-ex validate this, I think I can do this in argparse --- TODO
        email_to = args.email_to_override
    
    # Create Report Object
    r = OrderStatusReport()
    
    # Check each option and if set, grab info for it.  These are processed sequentially, and will display in this order, too.
    if args.runtimeinfo == True:
        i = OrderInfo("runtimeinfo")
        r.createReportSection("runtimeinfo", i.getResults())
    
    if args.orderinfo == True:
        i = OrderInfo("orderinfo")
        r.createReportSection("orderinfo", i.getResults())
    
    if args.failedscenes == True:
        i = OrderInfo("failedscenes")
        r.createReportSection("failedscenes", i.getResults())
    
    if args.onorderscenes == True:
        i = OrderInfo("onorderscenes")
        
        r.createReportSection("onorderscenes", i.getResults())
    
    if args.unavailablescenes == True:
        i = OrderInfo("unavailablescenes")
        r.createReportSection("unavailablescenes", i.getResults())    

    # Finalize the report for e-mailing    
    r.finalizeReport()

    # E-mail out the report, sucka!
    send_email(email_from, email_to, email_subject, r.finalReport)

if __name__ == '__main__':
    main()
