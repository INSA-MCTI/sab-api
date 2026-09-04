#!/usr/bin/env python
# -*- coding: utf-8 -*-
import IO
import funcoes_aux
from dateutil import relativedelta
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import abort
import math
import csv
import re

ALLOWED_EXTENSIONS = set(['csv'])
STATE_IDS = {
	"AL": 27,
	"BA": 29,
	"CE": 23,
	"MG": 31,
	"PB": 25,
	"PE": 26,
	"PI": 22,
	"RN": 24,
	"SE": 28,
}

def _date_to_numeric(date_string):
	return float(datetime.strptime(date_string, '%d/%m/%Y').toordinal())

def states_sab():
	return(IO.states_sab())

def json_brazil():
	return(IO.json_brazil())

def reservoirs():
	query = (
		"SELECT mon.id AS id_reservatorio, mon.latitude, mon.longitude, mon.capacidade, "
		"IF(mon.maior_data >= (CURDATE() - INTERVAL 90 DAY), ROUND(mo.volume_percentual,1), NULL) AS volume_percentual, "
		"IF(mon.maior_data >= (CURDATE() - INTERVAL 90 DAY), mo.volume, NULL) AS volume, "
		"IF(mon.maior_data >= (CURDATE() - INTERVAL 90 DAY), DATE_FORMAT(mon.maior_data,'%d/%m/%Y'), NULL) AS data_informacao, "
		"mo.fonte "
		"FROM ("
			"SELECT r.id, r.latitude, r.longitude, r.capacidade, MAX(m.data_informacao) AS maior_data "
			"FROM tb_reservatorio r "
			"LEFT JOIN tb_monitoramento m ON r.id = m.id_reservatorio "
			"GROUP BY r.id, r.latitude, r.longitude, r.capacidade"
		") mon "
		"LEFT JOIN tb_monitoramento mo ON mo.id_reservatorio = mon.id AND mo.data_informacao = mon.maior_data;"
	)
	select_answer = IO.select_DB(query)

	keys = ["id", "latitude", "longitude", "capacidade","volume_percentual","volume", "data_informacao", "fonte"]

	features = []
	for line in select_answer:
		feature = {}
		geometry = {}
		properties = funcoes_aux.create_dictionary(line, keys)

		geometry["type"] = "Point"
		geometry["coordinates"] = [float(properties["longitude"]),float(properties["latitude"])]

		feature["geometry"] = geometry
		feature["type"] = "Feature"
		feature["properties"] = properties

		features.append(feature)

	answer = {}
	answer["type"] = "FeatureCollection"
	answer["features"] = features

	return answer

def reservoirs_information(res_id=None):
	if (res_id is None):
		query = ("SELECT r.id,r.nome,r.perimetro,r.bacia,r.reservat,r.hectares"
				",r.tipo,r.area,r.capacidade,mv_mo.fonte"
				",mv_mo.volume, ROUND(mv_mo.volume_percentual,1), date_format(mv_mo.data_informacao,'%%d/%%m/%%Y')"
				",GROUP_CONCAT(DISTINCT m.nome SEPARATOR ' / ') municipio"
				",GROUP_CONCAT(DISTINCT e.nome SEPARATOR ' / ') estado"
				",GROUP_CONCAT(DISTINCT e.sigla SEPARATOR ' / ') uf"
				" FROM tb_reservatorio r JOIN tb_reservatorio_municipio rm ON r.id=rm.id_reservatorio"
				" JOIN tb_municipio m ON rm.id_municipio=m.id"
				" JOIN tb_estado e ON m.id_estado=e.id"
				" LEFT OUTER JOIN mv_monitoramento mv_mo"
				" ON mv_mo.id_reservatorio=r.id"
				" GROUP BY r.id,mv_mo.volume, mv_mo.volume_percentual,mv_mo.data_informacao")
		params = None
	else:
		query = ("SELECT r.id,r.nome,r.perimetro,r.bacia,r.reservat,r.hectares"
				",r.tipo,r.area,r.capacidade,mv_mo.fonte"
				",mv_mo.volume, ROUND(mv_mo.volume_percentual,1), date_format(mv_mo.data_informacao,'%d/%m/%Y')"
				",GROUP_CONCAT(DISTINCT m.nome SEPARATOR ' / ') municipio"
				",GROUP_CONCAT(DISTINCT e.nome SEPARATOR ' / ') estado"
				",GROUP_CONCAT(DISTINCT e.sigla SEPARATOR ' / ') uf"
				" FROM tb_reservatorio r JOIN tb_reservatorio_municipio rm ON r.id=rm.id_reservatorio AND r.id=%s"
				" JOIN tb_municipio m ON rm.id_municipio=m.id"
				" JOIN tb_estado e ON m.id_estado=e.id"
				" LEFT OUTER JOIN mv_monitoramento mv_mo"
				" ON mv_mo.id_reservatorio=r.id"
				" GROUP BY r.id,mv_mo.volume, mv_mo.volume_percentual,mv_mo.data_informacao")
		params = (int(res_id),)

	select_answer = IO.select_DB(query, params)
	
	keys = ["id","nome","perimetro","bacia","reservat","hectares","tipo","area","capacidade","fonte","volume","volume_percentual","data_informacao","municipio","estado", "uf"]

	return funcoes_aux.list_of_dictionarys(select_answer, keys, "info")

def reservoirs_monitoring(res_id,all_monitoring=False):
	if(all_monitoring):
		query = ("SELECT ROUND(mo.volume_percentual,1), date_format(mo.data_informacao,'%%d/%%m/%%Y'), mo.volume, mo.fonte FROM tb_monitoramento mo WHERE mo.id_reservatorio=%s"
			" ORDER BY mo.data_informacao")
	else:
		query = ("SELECT ROUND(mo.volume_percentual,1), date_format(mo.data_informacao,'%%d/%%m/%%Y'), mo.volume, mo.fonte FROM tb_monitoramento mo WHERE mo.visualizacao=1 and mo.id_reservatorio=%s"
			" ORDER BY mo.data_informacao")

	select_answer = IO.select_DB(query, (int(res_id),))

	keys = ["VolumePercentual","DataInformacao", "Volume","Fonte"]

	volumes_list = []
	dates_list = []
	months_monitoring = monitoring_months(res_id,6)
	last_month_monitoring = monitoring_months(res_id,1)
	date_final = datetime.strptime('31/12/1969', '%d/%m/%Y')

	for monitoring in last_month_monitoring:
		volumes_list.append(float(monitoring["Volume"]))
		date = datetime.strptime(monitoring["DataInformacao"], '%d/%m/%Y')
		if (date > date_final):
			date_final = date
		dates_list.append(_date_to_numeric(monitoring["DataInformacao"]))

	inicial_date = date_final - relativedelta.relativedelta(months=6)

	regression_coefficient=0
	if(len(volumes_list)>0):
		regression_gradient = funcoes_aux.regression_gradient(volumes_list,dates_list)
		if(not math.isnan(regression_gradient)):
			regression_coefficient=regression_gradient

	data_monitoring = funcoes_aux.fix_data_interval_limit(select_answer)

	return {'volumes': funcoes_aux.list_of_dictionarys(data_monitoring, keys), 'volumes_recentes':{'volumes':months_monitoring,
		'coeficiente_regressao': regression_coefficient, 'data_final':date_final.strftime('%d/%m/%Y'), 'data_inicial':inicial_date.strftime('%d/%m/%Y')}}

def reservoirs_monitoring_csv(res_id):
	monitoring_json = reservoirs_monitoring(res_id,True)
	volumes = monitoring_json["volumes"]
	saida = [['Volume','VolumePercentual','Fonte','DataInformacao']]
	for volume in volumes:
		if 'Fonte' in volume:
			saida.append([volume["Volume"], volume["VolumePercentual"], volume["Fonte"], volume["DataInformacao"]])
	return saida


def monitoring_months(res_id,months):
	months = int(months)
	query_min_graph = ("select ROUND(volume_percentual,1), date_format(data_informacao,'%%d/%%m/%%Y'), volume from tb_monitoramento where id_reservatorio = %s"
			" and visualizacao = 1 and data_informacao >= (CURDATE() - INTERVAL " + str(months) + " MONTH) order by data_informacao;")

	select_answer = IO.select_DB(query_min_graph, (int(res_id),))

	keys = ["VolumePercentual","DataInformacao", "Volume"]

	return funcoes_aux.list_of_dictionarys(select_answer,keys)


def reservoirs_similar(name, threshold):
	query = ("SELECT DISTINCT r.id,r.reservat,r.nome, date_format(mv_mo.data_informacao,'%d/%m/%Y'), ROUND(mv_mo.volume_percentual,1), mv_mo.volume, es.nome, es.sigla"
		" FROM mv_monitoramento mv_mo RIGHT JOIN tb_reservatorio r"
		" ON mv_mo.id_reservatorio=r.id LEFT JOIN tb_reservatorio_municipio re ON mv_mo.id_reservatorio= re.id_reservatorio"
		" LEFT JOIN tb_municipio mu ON mu.id= re.id_municipio LEFT JOIN tb_estado es ON es.id= mu.id_estado;")
	select_answer = IO.select_DB(query)

	keys = ["id", "reservat","nome", "data", "volume_percentual","volume", "nome_estado", "uf"]

	reservoirs = funcoes_aux.list_of_dictionarys(select_answer, keys)

	similar = funcoes_aux.reservoirs_similar(name,reservoirs,threshold)

	return similar

def reservoirs_states_monitoring_csv(uf):
	monitoring = reservoirs_equivalent_states_monitoring(uf)['volumes']
	keys = ['Volume','VolumePercentual','VolumeSemAgua','CapacidadeTotal','CapacidadeSemInfo','VolumePercentualTotal','VolumePercentualSemAgua',"total_reservatorios",'DataInformacao']
	return [keys] + [[row['Volume']] + [row['VolumePercentual']] + [row['VolumeSemAgua']] + [row['CapacidadeTotal']] + [row['CapacidadeSemInfo']] + [row['VolumePercentualTotal']] + [row['VolumePercentualSemAgua']] + [row['total_reservatorios']] + [row['DataInformacao']] for row in monitoring]

def reservoirs_equivalent_states_history(id_estado):
	estado_reservatorio = (
		"SELECT DISTINCT res.id AS id_reservatorio, es.id AS id_estado, es.nome AS estado, es.sigla AS sigla, "
		"CAST(res.capacidade AS DECIMAL(20,4)) AS capacidade_total_reservatorio "
		"FROM tb_reservatorio res "
		"JOIN tb_reservatorio_municipio rm ON res.id = rm.id_reservatorio "
		"JOIN tb_municipio mu ON rm.id_municipio = mu.id "
		"JOIN tb_estado es ON mu.id_estado = es.id"
	)
	if id_estado == 0 :
		query = (
			"SELECT DATE_FORMAT(mo.data_informacao,'%d/%m/%Y') AS data, "
			"ROUND(SUM(CAST(mo.volume AS DECIMAL(20,4))),2) AS volume_equivalente, "
			"ROUND(SUM(er.capacidade_total_reservatorio) - SUM(CAST(mo.volume AS DECIMAL(20,4))),2) AS volume_sem_agua, "
			"ROUND(SUM(er.capacidade_total_reservatorio),2) AS capacidade_equivalente, "
			"ROUND(total.capacidade_total - SUM(er.capacidade_total_reservatorio),2) AS capacidade_sem_info, "
			"ROUND(total.capacidade_total,2) AS capacidade_total, "
			"ROUND((SUM(CAST(mo.volume AS DECIMAL(20,4))) / NULLIF(SUM(er.capacidade_total_reservatorio),0)) * 100,2) AS porcentagem_equivalente, "
			"ROUND((SUM(CAST(mo.volume AS DECIMAL(20,4))) / NULLIF(total.capacidade_total,0)) * 100,2) AS porcentagem_total, "
			"ROUND(((SUM(er.capacidade_total_reservatorio) - SUM(CAST(mo.volume AS DECIMAL(20,4)))) / NULLIF(total.capacidade_total,0)) * 100,2) AS porcentagem_sem_agua, "
			"COUNT(DISTINCT mo.id_reservatorio) AS quant_reservatorio_com_info, "
			"(total.total_reservatorios - COUNT(DISTINCT mo.id_reservatorio)) AS quant_reservatorio_sem_info, "
			"total.total_reservatorios, "
			"COUNT(CASE WHEN CAST(mo.volume_percentual AS DECIMAL(10,2)) <= 10 THEN 1 END) AS intervalo_1, "
			"COUNT(CASE WHEN CAST(mo.volume_percentual AS DECIMAL(10,2)) > 10 AND CAST(mo.volume_percentual AS DECIMAL(10,2)) <= 25 THEN 1 END) AS intervalo_2, "
			"COUNT(CASE WHEN CAST(mo.volume_percentual AS DECIMAL(10,2)) > 25 AND CAST(mo.volume_percentual AS DECIMAL(10,2)) <= 50 THEN 1 END) AS intervalo_3, "
			"COUNT(CASE WHEN CAST(mo.volume_percentual AS DECIMAL(10,2)) > 50 AND CAST(mo.volume_percentual AS DECIMAL(10,2)) <= 75 THEN 1 END) AS intervalo_4, "
			"COUNT(CASE WHEN CAST(mo.volume_percentual AS DECIMAL(10,2)) > 75 THEN 1 END) AS intervalo_5 "
			"FROM tb_monitoramento mo "
			"JOIN (" + estado_reservatorio + ") er ON er.id_reservatorio = mo.id_reservatorio "
			"CROSS JOIN (SELECT ROUND(SUM(capacidade_total_reservatorio),4) AS capacidade_total, COUNT(*) AS total_reservatorios "
			"FROM (" + estado_reservatorio + ") estado_total) total "
			"GROUP BY mo.data_informacao, total.capacidade_total, total.total_reservatorios "
			"ORDER BY mo.data_informacao DESC;"
		)

		keys = ["data", "volume_equivalente","volume_sem_agua","capacidade_equivalente", "capacidade_sem_info","capacidade_total","porcentagem_equivalente", "porcentagem_total", "porcentagem_sem_agua", "quant_reservatorio_com_info","quant_reservatorio_sem_info",
	 	"total_reservatorios", "quant_reserv_intervalo_1", "quant_reserv_intervalo_2", "quant_reserv_intervalo_3", "quant_reserv_intervalo_4",
	  	"quant_reserv_intervalo_5"]
	else:
		query = (
			"SELECT DATE_FORMAT(mo.data_informacao,'%%d/%%m/%%Y') AS data, er.estado, er.sigla, "
			"ROUND(SUM(CAST(mo.volume AS DECIMAL(20,4))),2) AS volume_equivalente, "
			"ROUND(SUM(er.capacidade_total_reservatorio) - SUM(CAST(mo.volume AS DECIMAL(20,4))),2) AS volume_sem_agua, "
			"ROUND(SUM(er.capacidade_total_reservatorio),2) AS capacidade_equivalente, "
			"ROUND(total.capacidade_total - SUM(er.capacidade_total_reservatorio),2) AS capacidade_sem_info, "
			"ROUND(total.capacidade_total,2) AS capacidade_total, "
			"ROUND((SUM(CAST(mo.volume AS DECIMAL(20,4))) / NULLIF(SUM(er.capacidade_total_reservatorio),0)) * 100,2) AS porcentagem_equivalente, "
			"ROUND((SUM(CAST(mo.volume AS DECIMAL(20,4))) / NULLIF(total.capacidade_total,0)) * 100,2) AS porcentagem_total, "
			"ROUND(((SUM(er.capacidade_total_reservatorio) - SUM(CAST(mo.volume AS DECIMAL(20,4)))) / NULLIF(total.capacidade_total,0)) * 100,2) AS porcentagem_sem_agua, "
			"COUNT(DISTINCT mo.id_reservatorio) AS quant_reservatorio_com_info, "
			"(total.total_reservatorios - COUNT(DISTINCT mo.id_reservatorio)) AS quant_reservatorio_sem_info, "
			"total.total_reservatorios, "
			"COUNT(CASE WHEN CAST(mo.volume_percentual AS DECIMAL(10,2)) <= 10 THEN 1 END) AS intervalo_1, "
			"COUNT(CASE WHEN CAST(mo.volume_percentual AS DECIMAL(10,2)) > 10 AND CAST(mo.volume_percentual AS DECIMAL(10,2)) <= 25 THEN 1 END) AS intervalo_2, "
			"COUNT(CASE WHEN CAST(mo.volume_percentual AS DECIMAL(10,2)) > 25 AND CAST(mo.volume_percentual AS DECIMAL(10,2)) <= 50 THEN 1 END) AS intervalo_3, "
			"COUNT(CASE WHEN CAST(mo.volume_percentual AS DECIMAL(10,2)) > 50 AND CAST(mo.volume_percentual AS DECIMAL(10,2)) <= 75 THEN 1 END) AS intervalo_4, "
			"COUNT(CASE WHEN CAST(mo.volume_percentual AS DECIMAL(10,2)) > 75 THEN 1 END) AS intervalo_5 "
			"FROM tb_monitoramento mo "
			"JOIN (" + estado_reservatorio + ") er ON er.id_reservatorio = mo.id_reservatorio "
			"JOIN (SELECT id_estado, ROUND(SUM(capacidade_total_reservatorio),4) AS capacidade_total, COUNT(*) AS total_reservatorios "
			"FROM (" + estado_reservatorio + ") estado_total GROUP BY id_estado) total ON total.id_estado = er.id_estado "
			"WHERE er.id_estado = %s "
			"GROUP BY mo.data_informacao, er.estado, er.sigla, total.capacidade_total, total.total_reservatorios "
			"HAVING SUM(CAST(mo.volume AS DECIMAL(20,4))) > 0 "
			"ORDER BY mo.data_informacao DESC;"
		)

		keys = ["data","estado", "uf", "volume_equivalente","volume_sem_agua","capacidade_equivalente", "capacidade_sem_info","capacidade_total" ,"porcentagem_equivalente","porcentagem_total", "porcentagem_sem_agua", "quant_reservatorio_com_info","quant_reservatorio_sem_info",
	 	"total_reservatorios", "quant_reserv_intervalo_1", "quant_reserv_intervalo_2", "quant_reserv_intervalo_3", "quant_reserv_intervalo_4",
	  	"quant_reserv_intervalo_5"]
	params = None if id_estado == 0 else (int(id_estado),)
	select_answer = IO.select_DB(query, params)


	list_dictionarys = funcoes_aux.list_of_dictionarys(select_answer, keys)


	return list_dictionarys


def reservoirs_equivalent_states_monitoring(uf="Semiarido"):

	list_dic = []
	list_dic_2 = []
	dates_list = []
	date_final = None
	inicial_date = None
	volumes_list = []
	id_estado = STATE_IDS.get(uf, 0)

	keys_recentes = ["VolumePercentual","DataInformacao", "Volume"]
	keys = ['Volume','VolumePercentual','VolumeSemAgua','CapacidadeTotal','CapacidadeSemInfo','VolumePercentualTotal','VolumePercentualSemAgua',"total_reservatorios","quant_reservatorio_com_info","quant_reservatorio_sem_info","quant_reserv_intervalo_1","quant_reserv_intervalo_2","quant_reserv_intervalo_3","quant_reserv_intervalo_4","quant_reserv_intervalo_5",'DataInformacao']

	dic = reservoirs_equivalent_states_history(id_estado)

	# dic vem ordenado DESC (mais recente primeiro) do banco.
	# Invertemos para ordem cronológica crescente (mais antigo primeiro).
	for elem in reversed(dic):
		date = datetime.strptime(elem["data"], '%d/%m/%Y')
		if date_final is None or date > date_final:
			date_final = date
		if inicial_date is None or date < inicial_date:
			inicial_date = date
		if elem["porcentagem_equivalente"] is not None:
			dates_list.append(float(date.toordinal()))
			volumes_list.append(elem["porcentagem_equivalente"])
		value = [elem["porcentagem_equivalente"], elem["data"], elem["volume_equivalente"]]
		value_2 = [elem["volume_equivalente"],elem["porcentagem_equivalente"],elem["volume_sem_agua"],elem["capacidade_total"],elem["capacidade_sem_info"],elem["porcentagem_total"],elem["porcentagem_sem_agua"],elem["total_reservatorios"],elem["quant_reservatorio_com_info"],elem["quant_reservatorio_sem_info"],elem["quant_reserv_intervalo_1"],elem["quant_reserv_intervalo_2"],elem["quant_reserv_intervalo_3"],elem["quant_reserv_intervalo_4"],elem["quant_reserv_intervalo_5"],elem["data"]]
		list_dic.append(value)
		list_dic_2.append(value_2)

	regression_coefficient=0
	if volumes_list and len(volumes_list) == len(dates_list):
		regression_gradient = funcoes_aux.regression_gradient(volumes_list,dates_list)
		if(not math.isnan(regression_gradient)):
			regression_coefficient=regression_gradient

	if date_final is None:
		date_final = datetime.today()
	if inicial_date is None:
		inicial_date = date_final

	# volumes_recentes: últimos 6 registros (mais antigos) + o mais recente.
	# Isso faz o gráfico terminar exatamente no mesmo ponto do volume atual exibido no painel.
	recent_slice = list_dic[-7:] if len(list_dic) >= 7 else list_dic

	return {'volumes': funcoes_aux.list_of_dictionarys(list_dic_2, keys),'volumes_recentes':{'volumes':funcoes_aux.list_of_dictionarys(recent_slice, keys_recentes),
		'coeficiente_regressao': regression_coefficient, 'data_final':date_final.strftime('%d/%m/%Y'), 'data_inicial':inicial_date.strftime('%d/%m/%Y')}}

def reservoirs_equivalent_hydrographic_basin():
	query = ("SELECT res.bacia AS bacia, ROUND(SUM(mv_mo.volume),2) AS volume_equivalente, ROUND(SUM(mv_mo.capacidade),2) AS capacidade_equivalente,"
		" ROUND((SUM(mv_mo.volume)/SUM(mv_mo.capacidade)*100),1) AS porcentagem_equivalente,"
		" COUNT(DISTINCT mv_mo.id_reservatorio) AS quant_reservatorio_com_info,"
		" (COUNT(DISTINCT res.id)-COUNT(DISTINCT mv_mo.id_reservatorio)) AS quant_reservatorio_sem_info ,COUNT(DISTINCT res.id) AS total_reservatorios,"
		" COUNT(CASE WHEN mv_mo.volume_percentual <= 10 THEN 1 ELSE 0 END) AS intervalo_1,"
		" COUNT(CASE WHEN mv_mo.volume_percentual > 10 AND mv_mo.volume_percentual <=25 THEN 1 END) AS intervalo_2,"
		" COUNT(CASE WHEN mv_mo.volume_percentual > 25 AND mv_mo.volume_percentual <=50 THEN 1 END) AS intervalo_3,"
		" COUNT(CASE WHEN mv_mo.volume_percentual > 50 AND mv_mo.volume_percentual <=75 THEN 1 END) AS intervalo_4,"
		" COUNT(CASE WHEN mv_mo.volume_percentual > 75 THEN 1 END) AS intervalo_5"
		" FROM tb_reservatorio res LEFT JOIN mv_monitoramento mv_mo"
		" ON mv_mo.data_informacao  >= (CURDATE() - INTERVAL 90 DAY) AND mv_mo.id_reservatorio=res.id GROUP BY res.bacia;")

	select_answer = IO.select_DB(query)

	keys = ["bacia", "volume_equivalente","capacidade_equivalente", "porcentagem_equivalente", "quant_reservatorio_com_info","quant_reservatorio_sem_info",
	 "total_reservatorios", "quant_reserv_intervalo_1", "quant_reserv_intervalo_2", "quant_reserv_intervalo_3", "quant_reserv_intervalo_4",
	  "quant_reserv_intervalo_5"]

	return funcoes_aux.list_of_dictionarys(select_answer, keys)


def reservoirs_equivalent_states():
	query = ("SELECT estado_reservatorio.estado_nome AS estado, estado_reservatorio.estado_sigla AS sigla, ROUND(SUM(mv_mo.volume),2) AS volume_equivalente,"
		" ROUND(SUM(mv_mo.capacidade),2) AS capacidade_equivalente, ROUND((SUM(mv_mo.volume)/SUM(mv_mo.capacidade)*100),1) AS porcentagem_equivalente,"
		" COUNT(DISTINCT mv_mo.id_reservatorio) AS quant_reservatorio_com_info,"
		" (COUNT(DISTINCT estado_reservatorio.id_reservatorio)-COUNT(DISTINCT mv_mo.id_reservatorio)) AS quant_reservatorio_sem_info,"
		" COUNT(DISTINCT estado_reservatorio.id_reservatorio) AS total_reservatorios,"
		" COUNT(CASE WHEN mv_mo.volume_percentual <= 10 THEN 1 END) AS intervalo_1,"
		" COUNT(CASE WHEN mv_mo.volume_percentual > 10 AND mv_mo.volume_percentual <=25 THEN 1 END) AS intervalo_2,"
		" COUNT(CASE WHEN mv_mo.volume_percentual > 25 AND mv_mo.volume_percentual <=50 THEN 1 END) AS intervalo_3,"
		" COUNT(CASE WHEN mv_mo.volume_percentual > 50 AND mv_mo.volume_percentual <=75 THEN 1 END) AS intervalo_4,"
		" COUNT(CASE WHEN mv_mo.volume_percentual > 75 THEN 1 END) AS intervalo_5"
		" FROM mv_monitoramento mv_mo RIGHT JOIN (select distinct res.id as id_reservatorio, es.nome as estado_nome, es.sigla as estado_sigla"
		" FROM tb_reservatorio res, tb_reservatorio_municipio rm, tb_municipio mu, tb_estado es"
		" WHERE res.id=rm.id_reservatorio and mu.id=rm.id_municipio and mu.id_estado=es.id) estado_reservatorio"
		" ON estado_reservatorio.id_reservatorio=mv_mo.id_reservatorio AND mv_mo.data_informacao >= (CURDATE() - INTERVAL 90 DAY)"
		" GROUP BY estado_reservatorio.estado_nome, estado_reservatorio.estado_sigla;")

	select_answer = IO.select_DB(query)

	keys = ["estado", "uf", "volume_equivalente","capacidade_equivalente", "porcentagem_equivalente", "quant_reservatorio_com_info","quant_reservatorio_sem_info",
	 "total_reservatorios", "quant_reserv_intervalo_1", "quant_reserv_intervalo_2", "quant_reserv_intervalo_3", "quant_reserv_intervalo_4",
	  "quant_reserv_intervalo_5"]

	list_dictionarys = funcoes_aux.list_of_dictionarys(select_answer, keys)

	# Semiarido Brasileiro
	volume_equivalente = 0
	capacidade_equivalente = 0
	quant_reservatorio_com_info = 0
	quant_reservatorio_sem_info = 0
	total_reservatorios = 0
	quant_reserv_intervalo_1 = 0
	quant_reserv_intervalo_2 = 0
	quant_reserv_intervalo_3 = 0
	quant_reserv_intervalo_4 = 0
	quant_reserv_intervalo_5 = 0

	for i in range(len(list_dictionarys)):
		if(list_dictionarys[i]["uf"] == "AL"):
			list_dictionarys[i]["semiarido"] = "Semiárido Alagoano"
		elif(list_dictionarys[i]["uf"] == "PE"):
			list_dictionarys[i]["semiarido"] = "Semiárido Pernambucano"
		elif(list_dictionarys[i]["uf"] == "BA"):
			list_dictionarys[i]["semiarido"] = "Semiárido Baiano"
		elif(list_dictionarys[i]["uf"] == "PB"):
			list_dictionarys[i]["semiarido"] = "Semiárido Paraibano"
		elif(list_dictionarys[i]["uf"] == "CE"):
			list_dictionarys[i]["semiarido"] = "Semiárido Cearense"
		elif(list_dictionarys[i]["uf"] == "MG"):
			list_dictionarys[i]["semiarido"] = "Semiárido Mineiro"
		elif(list_dictionarys[i]["uf"] == "PI"):
			list_dictionarys[i]["semiarido"] = "Semiárido Piauiense"
		elif(list_dictionarys[i]["uf"] == "SE"):
			list_dictionarys[i]["semiarido"] = "Semiárido Sergipano"
		elif(list_dictionarys[i]["uf"] == "RN"):
			list_dictionarys[i]["semiarido"] = "Semiárido Potiguar"
		volume_equivalente = volume_equivalente + (list_dictionarys[i]["volume_equivalente"] if list_dictionarys[i]["volume_equivalente"] is not None else 0)
		capacidade_equivalente = capacidade_equivalente + (list_dictionarys[i]["capacidade_equivalente"] if list_dictionarys[i]["capacidade_equivalente"] is not None else 0)
		quant_reservatorio_com_info = quant_reservatorio_com_info + list_dictionarys[i]["quant_reservatorio_com_info"]
		quant_reservatorio_sem_info = quant_reservatorio_sem_info + list_dictionarys[i]["quant_reservatorio_sem_info"]
		total_reservatorios = total_reservatorios + list_dictionarys[i]["total_reservatorios"]
		quant_reserv_intervalo_1 = quant_reserv_intervalo_1 + list_dictionarys[i]["quant_reserv_intervalo_1"]
		quant_reserv_intervalo_2 = quant_reserv_intervalo_2 + list_dictionarys[i]["quant_reserv_intervalo_2"]
		quant_reserv_intervalo_3 = quant_reserv_intervalo_3 + list_dictionarys[i]["quant_reserv_intervalo_3"]
		quant_reserv_intervalo_4 = quant_reserv_intervalo_4 + list_dictionarys[i]["quant_reserv_intervalo_4"]
		quant_reserv_intervalo_5 = quant_reserv_intervalo_5 + list_dictionarys[i]["quant_reserv_intervalo_5"]

	porcentagem_equivalente = 0
	if capacidade_equivalente:
		porcentagem_equivalente = round(volume_equivalente/capacidade_equivalente*100,1)

	list_dictionarys.append({"estado":"Semiarido", "uf":"Semiarido","semiarido":"Semiárido Brasileiro", "volume_equivalente":round(volume_equivalente,2),
		"capacidade_equivalente":round(capacidade_equivalente,2), "porcentagem_equivalente":porcentagem_equivalente,
		"quant_reservatorio_com_info":quant_reservatorio_com_info,"quant_reservatorio_sem_info":quant_reservatorio_sem_info,
		"total_reservatorios":total_reservatorios, "quant_reserv_intervalo_1":quant_reserv_intervalo_1, "quant_reserv_intervalo_2":quant_reserv_intervalo_2,
		 "quant_reserv_intervalo_3":quant_reserv_intervalo_3, "quant_reserv_intervalo_4":quant_reserv_intervalo_4,
		 "quant_reserv_intervalo_5":quant_reserv_intervalo_5})

	return list_dictionarys
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def verify_csv(req):
	reservatId = req.values["reservatId"]
	if 'file' not in req.files:
	    abort (404)
	file = req.files['file']
	if file.filename == '':
	    abort (404)
	isValido = False
	monitoramentoList = []
	saida = {"valido": False, "arquivo": "", "linhas": 0}
	if file and allowed_file(file.filename):
	    filename = secure_filename(file.filename)
	    monitoramento = file.read()
	    if isinstance(monitoramento, bytes):
	        monitoramento = monitoramento.decode("utf-8")
	    isValido = True
	    regex = re.compile(r"^\d+(\.\d+)?,\d+(\.\d+)?,[A-Z ]*,\d{2}/\d{2}/\d{4}$")
	    monitoramentoList = [line.strip() for line in monitoramento.splitlines() if line.strip()]
	    for i in range(1, len(monitoramentoList)):
	        if regex.search(monitoramentoList[i]) is None:
	            isValido = False
	    saida = {"valido": isValido, "arquivo": file.filename, "linhas":len(monitoramentoList)}
	if isValido:
		temporary_upload(reservatId, monitoramentoList)
	return saida

def temporary_upload(reservatId, lines):
	IO.delete_DB_upload()
	values = []
	#id_reservatorio,cota,volume,volume_percentual,data_informacao,visualizacao,fonte
	for value in lines[1:]:
		aux = [reservatId] + value.split(',')
		values.append([int(reservatId),'',float(aux[1]),float(aux[2]),datetime.strptime(aux[4], '%d/%m/%Y').strftime('%Y-%m-%d'),1,aux[3]])
	IO.insert_many_BD_upload(values)

def confirm_upload(req,reservatId):
	# reservatId = req.values["reservatId"]
	return {'replaced' : IO.replace_reservat_history(reservatId)}

def city_info(sab=0):
	query = ("SELECT mu.id, mu.nome, mu.latitude,mu.longitude, es.sigla, es.nome"
		" FROM tb_municipio mu JOIN tb_estado es ON es.id=mu.id_estado WHERE semiarido=%s;")
	select_answer = IO.select_DB(query, (int(sab),))

	keys = ["id_municipio","nome_municipio","latitude","longitude","UF","estado"]

	return funcoes_aux.list_of_dictionarys(select_answer, keys)

def search_information():
	query = ("SELECT r.id,r.nome,r.reservat as nome_exibicao,r.bacia,r.reservat"
		",GROUP_CONCAT(DISTINCT m.nome SEPARATOR ' / ') municipio"
		" FROM tb_reservatorio r JOIN tb_reservatorio_municipio rm ON r.id=rm.id_reservatorio"
		" JOIN tb_municipio m ON rm.id_municipio=m.id"
		" GROUP BY r.id;")

	select_answer = IO.select_DB(query)

	keys = ["id","nome", "nome_exibicao", "bacia","reservat","municipio"]

	answer = funcoes_aux.list_of_dictionarys(select_answer, keys, "info")

	query_2 = ("SELECT m.id,m.nome, CONCAT_WS(' - ', m.nome, e.sigla) nome_exibicao"
		" FROM tb_municipio m JOIN tb_estado e ON m.id_estado=e.id and m.semiarido=1")

	select_answer_2 = IO.select_DB(query_2)

	keys_2 = ["id","nome","nome_exibicao"]

	answer.extend(funcoes_aux.list_of_dictionarys(select_answer_2, keys_2, "mun"))

	return answer
