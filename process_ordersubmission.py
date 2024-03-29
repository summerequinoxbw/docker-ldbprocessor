#!/usr/bin/env python

__author__ = "David Rickett"
__credits__ = ["David Rickett"]
__license__ = "GPL"
__version__ = "1.0.1"
__maintainer__ = "David Rickett"
__email__ = "dap.rickett@gmail.com"
__status__ = "Production"

#"LDB Stocked Product Expected for Delivery"
#"Third Party Warehouse Stocked Product Currently Unavailable"
#end at "Subtotal:"

import json
import sys
import re
import time
import datetime
from datetime import date
#import pymysql
from mysql.connector import (connection)

DIRECTORY='/var/ldbinvoice'
PB_FILE='processedbarcodes.json'

MYSQL_IP='127.0.0.1'
MYSQL_PORT=3306
MYSQL_USER=None
MYSQL_PASS=None
MYSQL_DB=None
REDIS_IP='127.0.0.1'
REDIS_PORT=6783

cnx=None

logtable=['orderlog']

keys='SKU,UPC,PRODUCT DESCRIPTION,SELLING UNITSIZE,UOM,QTY'

itemlist = []
itemlistnonstock = []
itemlist3rdparty = []
itemlist3rdpartynonstock = []
append=0

orderline = re.compile('Order #:, ?\d{4,}$')
orderdateline = re.compile('Order Booking Date *, *\d{8},$')
ordershipdateline = re.compile('Expected Ship Date *, *\d{8},$')

dollarvalue = re.compile('\$\d+,\d{3}')

itemlistline = re.compile('^\d{8}')

itemlineok = re.compile('\d+,\d+,[\w\d \.]+,(\d{1,3}\()?[\w\d \.]+\)?,(CS|BTL),\d+')

def getorderfromdatabase(ordernumber):

	if ordernumber == 'NaN':
		return

	cursor = cnx.cursor(buffered=True)

#	query = ("SELECT price, lastupdated FROM pricechangelist WHERE sku=%s"%(sku))
	query = f'SELECT sku, upc, qty FROM orderlog WHERE ordernumber={ordernumber}'
	cursor.execute(query)

	rows = cursor.fetchall()
	order = {}
	for row in rows:
		sku, upc, qty = row
		order[f'{sku}'] = {}
		order[f'{sku}']['sku'] = sku
		order[f'{sku}']['upc'] = upc
		order[f'{sku}']['qty'] = qty
#		print(('%s (%s) x %s')%(sku.zfill(6), upc, qty))
		print(f"{order[{ordernumber}]['sku']:06} ({order[{ordernumber}]['upc']}) x {order[f'{ordernumber}']['qty']}")

	cursor.close()

	return order

def insertintodatabase(line, table, ordnum, orddate, thirdparty):
	cursor = cnx.cursor(buffered=True)

	if( itemlineok.match(line) is None ):
		print( f'Line failed validation:\n\t{line}' )
		return;

	linesplit = line.split(',')

	sku = linesplit[0].strip()
	upc = linesplit[1].strip()
	productdescription = linesplit[2].strip()
	sellingunitsize = linesplit[3].strip()
	uom = linesplit[4].strip()
	qty = linesplit[5].strip()

	query = f'''INSERT INTO orderlog (
		ordernumber, orderdate, sku, upc, productdescription, sellingunitsize, uom, qty, thirdparty ) VALUES ( {ordnum}, {orddate}, {sku}, {upc}, '{productdescription}', '{sellingunitsize}', '{uom}', '{qty}', {thirdparty} )
		'''

#	print(query)
	cursor.execute(query)
	cnx.commit()
	cursor.close()

def processCSV(file):
	ordernum = 0
	orderdate = 0
	ordershipdate = 0
	with open(file) as f:
		for line in f:

		#check if any dollar values exceed $999

	#		p = re.compile('\$\d+,\d{3}')
	#		m = p.match(line)
			if( dollarvalue.match(line) is not None ):
				print( dollarvalue.group() )
				line.replace(m.group(), m.group().replace(',',''))

			#strip all non-alphanumeric characters and whitespace greater than 2

			line = re.sub('([^ \sa-zA-Z0-9.,]| {2,})','',line).strip()

	#		if( append == 0 ):
	#			print( line )

			#regex find the order number, date, and expected ship date
			ols = orderline.search(line)
			if( ols is not None ):
				print(line)
				ordernum = ols.group(0).split(',')[1].strip()
				print(ordernum)
			odls = orderdateline.search(line)
			if( odls is not None ):
				print(line)
				orderdate = odls.group(0).split(',')[1].strip()
				print(orderdate)
			osdls = ordershipdateline.search(line)
			if( osdls is not None ):
				print(line)
				ordershipdate = osdls.group(0).split(',')[1].strip()
				print(ordershipdate)

			#find and fill table

			if( line.find('LDB Stocked Product Expected for Delivery') > -1):
				append=1
			elif( line.find('LDB Stocked Product Currently Unavailable') > -1):
				append=2
			elif( line.find('Third Party Warehouse Stocked Product on Order') > -1):
				append=4
			elif( line.find('Third Party Warehouse Stocked Product Currently Unavailable') > -1):
				append=8

			if( append > 0 ):
				line = re.sub('([^ \sa-zA-Z0-9.,]| {2,})','',line)
				line = re.sub( '( , |, | ,)', ',', line)
				line = re.sub( '(,,|, ,)', ',0.00,', line )

			if( append == 1 ):
				if( itemlistline.match(line) is not None ):
					insertintodatabase(line,0,ordernum,orderdate,False)
	#				itemlist.append(line)
	#				print( line )
	#		elif( append == 2 ):
	#			if( itemlistline.match(line) is not None ):
	#				insertintodatabase(line,0,ordernum,orderdate)
	#				itemlistnonstock.append(line)
	#				print( line )
			elif( append == 4 ):
				if( itemlistline.match(line) is not None ):
					insertintodatabase(line,0,ordernum,orderdate,True)
	#				itemlist3rdparty.append(line)
	#				print( line )
	#		elif( append == 8 ):
	#			if( itemlistline.match(line) is not None ):
	#				insertintodatabase(line,0,ordernum,orderdate)
	#				itemlist3rdpartynonstock.append(line)
	#				print( line )

	#for item in itemlist:
	#	print( item )
	#for item in itemlist2wk:
	#	print( item )

	#print( list )

	#with open('/tmp/Order_' + list['OrderNumber']+'.json', 'w') as fp:
	#	json.dump(list,fp,indent=4,separators=(',', ': '),sort_keys=True)

	return ordernum, orderdate, ordershipdate


def mysql_setup():
	global cnx
	cnx = connection.MySQLConnection(user=MYSQL_USER, password=MYSQL_PASS,
				host=MYSQL_IP,
				port=MYSQL_PORT,
				database=MYSQL_DB)

	cur = cnx.cursor(buffered=True)
	cur.execute('''CREATE TABLE IF NOT EXISTS orderlog (
		id INT NOT NULL AUTO_INCREMENT,
		sku MEDIUMINT(8) ZEROFILL,
		upc BIGINT UNSIGNED,
		productdescription VARCHAR(255),
		sellingunitsize VARCHAR(32),
		uom VARCHAR(20),
		qty SMALLINT UNSIGNED,
		orderdate INT(8) UNSIGNED,
		ordernumber INT UNSIGNED,
		thirdparty BOOL,
		PRIMARY KEY (id))''')
	cnx.commit()
	cur.close()


def importconfig(file):
	return 0

def main(file, outdir, **kwargs):
	print('Called myscript with:')
	for k, v in kwargs.items():
		print('keyword argument: {} = {}'.format(k, v))

	global MYSQL_USER
	global MYSQL_PASS
	global MYSQL_IP
	global MYSQL_PORT
	global MYSQL_DB
	global REDIS_IP
	global REDIS_PORT

	#import a config file
	if 'configfile' in kwargs:
		importconfig(kwargs['configfile'])

	if 'MYSQL_USER' in kwargs:
		MYSQL_USER = kwargs['MYSQL_USER']
	if 'MYSQL_PASS' in kwargs:
		MYSQL_PASS = kwargs['MYSQL_PASS']
	if 'MYSQL_IP' in kwargs:
		MYSQL_IP = kwargs['MYSQL_IP']
	if 'MYSQL_PORT' in kwargs:
		MYSQL_PORT = int(kwargs['MYSQL_PORT'])
	if 'MYSQL_DB' in kwargs:
		MYSQL_DB = kwargs['MYSQL_DB']
	if 'REDIS_IP' in kwargs:
		REDIS_IP = kwargs['REDIS_IP']
	if 'REDIS_PORT' in kwargs:
		REDIS_PORT = int(kwargs['REDIS_PORT'])

	mysql_setup()
	order = {}
	order['ordernum'], order['orderdate'], order['ordershipdate'] = processCSV(file)

	with open(f"{outdir}/order{order['ordernum'}.txt", 'w') as fp:
		json.dump({**order, **getorderfromdatabase(ordernum)},fp,indent=4,separators=(',', ': '),sort_keys=True)
	cnx.close()

if __name__=='__main__':
	main(sys.argv[1], sys.argv[2], **dict(arg.split('=') for arg in sys.argv[3:])) # kwargs
