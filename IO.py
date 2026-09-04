#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import MySQLdb


path_local = os.path.dirname(os.path.realpath(__file__))
MYSQL_DEFAULT_FILE = os.path.join(path_local, 'my.cnf')


with open(path_local+'/data/topojson/semiarido.json', encoding='utf-8') as data_file:
	_state_division_sab = json.load(data_file)

def states_sab():
	"""return a json"""
	return _state_division_sab

with open(path_local+'/data/brasil.json', encoding='utf-8') as data_file:
	_json_brazil = json.load(data_file)

def json_brazil():
	"""return a json"""
	return _json_brazil

def delete_DB_upload():
	try:
		conn = MySQLdb.connect(read_default_file=MYSQL_DEFAULT_FILE, read_default_group='INSA',db="INSA")
		cursor = conn.cursor()

		cursor.execute("truncate tb_monitoramento_upload;")
		conn.commit()

	finally:
		cursor.close()
		conn.close()

def replace_reservat_history(reservatId):
	conn = MySQLdb.connect(read_default_file=MYSQL_DEFAULT_FILE, read_default_group='INSA',db="INSA")
	cursor = conn.cursor()
	ret = False
	try:
		cursor.execute("CALL replace_reservat_history(%s);", (reservatId,))
		conn.commit()
		ret = True
	finally:
		cursor.close()
		conn.close()
	return ret

def insert_many_BD_upload(values):
	conn = MySQLdb.connect(read_default_file=MYSQL_DEFAULT_FILE, read_default_group='INSA',db="INSA")
	cursor = conn.cursor()
	try:
		cursor.executemany("""INSERT INTO tb_monitoramento_upload (id_reservatorio,cota,volume,volume_percentual,data_informacao,visualizacao,fonte) VALUES (%s,%s,%s,%s,%s,%s,%s)""", values)
		conn.commit()
	except MySQLdb.Error as e:
		print("Error", e)
		conn.rollback()

	cursor.close()
	conn.close()

def select_DB(query, params=None):
	""" Connect to MySQL database """
	try:
		conn = MySQLdb.connect(read_default_file=MYSQL_DEFAULT_FILE, read_default_group='INSA',db="INSA")
		cursor = conn.cursor()

		if params is None:
			cursor.execute(query)
		else:
			cursor.execute(query, params)

		rows = cursor.fetchall()

	finally:
		cursor.close()
		conn.close()

	return rows

def select_one_DB(query, params=None):
	""" Connect to MySQL database """
	try:
		conn = MySQLdb.connect(read_default_file=MYSQL_DEFAULT_FILE, read_default_group='INSA',db="INSA")
		cursor = conn.cursor()

		if params is None:
			cursor.execute(query)
		else:
			cursor.execute(query, params)

		rows = cursor.fetchone()

	finally:
		cursor.close()
		conn.close()

	return rows
