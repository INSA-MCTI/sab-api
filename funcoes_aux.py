#!/usr/bin/env python
# -*- coding: utf-8 -*-

from unicodedata import normalize
from dateutil import relativedelta
from datetime import date, datetime
from decimal import Decimal
from fuzzywuzzy import fuzz
import re
from scipy import stats
import sys
import os
BASE_DIR = os.path.dirname(os.path.realpath(__file__))
PREDICT_DIR = os.path.join(BASE_DIR, 'predict')
if PREDICT_DIR not in sys.path:
	sys.path.insert(0, PREDICT_DIR)
import predict
import predict_info
import IO



def remove_accents(txt):
	if isinstance(txt, bytes):
		txt = txt.decode("utf-8")
	return normalize('NFKD', txt).encode('ASCII','ignore').decode('ASCII')

def fix_accents(txt):
	if isinstance(txt, bytes):
		return txt.decode('unicode-escape')
	return bytes(txt, 'utf-8').decode('unicode-escape')

def list_of_dictionarys(list_of_values, keys, especial=None):
	answer_list = []
	dias = 0

	for value in list_of_values:
		dictionary = create_dictionary(value,keys)
		if (especial == "info"):
			dictionary["nome_sem_acento"] = remove_accents(dictionary["nome"])
			dictionary["reservat_sem_acento"] = remove_accents(dictionary["reservat"])
			dictionary["tipo"] = "reservatorio"
			# if "uf" in dictionary:
			# 	if dictionary["uf"] == 'PB' and dictionary["volume"] != None:
			# 		previsao = predict.calcula(dictionary)
			# 		if previsao != None:
			# 			dias = str(previsao)
			# 		else:
			# 			dias = "NULL"
			# 	else:
			# 		dias = "NULL"
			# 	dictionary["previsao"] = dias
			# 	dictionary["volume_morto"] = "%.2f" % round((predict_info.volumeMorto(dictionary["id"]) / 1000000.0), 2)
		if (especial == "mun"):
			dictionary["nome_sem_acento"] = remove_accents(dictionary["nome"])
			dictionary["tipo"] = "municipio"
		answer_list.append(normalize_json_value(dictionary))

	return answer_list

def normalize_json_value(value):
	if isinstance(value, Decimal):
		return float(value)
	if isinstance(value, (datetime, date)):
		return value.isoformat()
	if isinstance(value, bytes):
		return value.decode("utf-8")
	if isinstance(value, dict):
		return {key: normalize_json_value(item) for key, item in value.items()}
	if isinstance(value, list):
		return [normalize_json_value(item) for item in value]
	if isinstance(value, tuple):
		return tuple(normalize_json_value(item) for item in value)
	return value

def create_dictionary(values, keys):
	dictionary = {}
	for i in range(len(values)):
		dictionary[keys[i]] = normalize_json_value(values[i])
	return dictionary

def fix_data_interval_limit(monitoring):
	result = []
	range_days = relativedelta.relativedelta(days=90)
	day = relativedelta.relativedelta(days=1)
	for m in range(len(monitoring)-1):
		result.append(monitoring[m])
		if(datetime.strptime(monitoring[m][1], "%d/%m/%Y") <= (datetime.strptime(monitoring[m+1][1], "%d/%m/%Y")- range_days)):
			empty_date_inicial = (datetime.strptime(monitoring[m][1], "%d/%m/%Y")+day).strftime("%d/%m/%Y")
			empty_date_final = (datetime.strptime(monitoring[m+1][1], "%d/%m/%Y")-day).strftime("%d/%m/%Y")
			result.append((None,monitoring[m][1],None))
			result.append((None,monitoring[m+1][1],None))
	if(len(monitoring) > 0):
		result.append(monitoring[len(monitoring)-1])

	return result

def reservoirs_similar(reservoir_name, reservoirs, threshold):
	reservoirs_list = []

	for reserv in reservoirs:
		reserv["apelido"] = re.sub(remove_accents(reserv["nome"])+'|acude|barragem|lagoa|[()-]| do | da | de ','',remove_accents(reserv["reservat"]), flags=re.IGNORECASE).strip()
		similar_reservat = fuzz.token_set_ratio(remove_accents(reservoir_name),remove_accents(reserv["reservat"]))
		similar_name = fuzz.token_set_ratio(remove_accents(reservoir_name),remove_accents(reserv["nome"]))
		similar_nickname = fuzz.token_set_ratio(remove_accents(reservoir_name),remove_accents(reserv["apelido"]))

		reserv["semelhanca"] = max(similar_reservat,similar_name,similar_nickname)

		reservoirs_list.append(reserv)

	# Pega os 5 mais semelhantes
	reservoirs_list_ordered = sorted(reservoirs_list, key=lambda k: k['semelhanca'], reverse=True)

	# Filtra os 100% semelhantes
	reservoirs_list_filtered = list(filter(lambda d: d['semelhanca'] == 100, reservoirs_list_ordered))

	# Se não tiver nenhum 100% semelhante retorna os 5 primeiros, caso contrário os semelhantes
	if(len(reservoirs_list_filtered) > 0):
		return reservoirs_list_filtered
	else:
		return list(filter(lambda d: d['semelhanca'] >= threshold, reservoirs_list_ordered))[:5]

def regression_gradient(list_1,list_2):
	if not hasattr(list_1, '__iter__') or not hasattr(list_2, '__iter__'):
		return 0
	values_1 = [float(value) for value in list_1]
	values_2 = [float(value) for value in list_2]
	if len(values_1) != len(values_2) or len(values_1) < 2:
		return 0
	gradient, intercept, r_value, p_value, std_err = stats.linregress(values_1, values_2)
	return gradient

def get_last_date(reservoir_id):
	return IO.select_DB("select data_informacao from mv_monitoramento where id_reservatorio = " + reservoir_id +" ;" )[0][0]
