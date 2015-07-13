#!/usr/bin/python

import arcpy, math, sets


# Calculates the minimum lot sizes for each zone
def minimumLotSize(zoningData, outputWorkspace):

	carney_codes = {"RR-2" : 30000, "RR-1" : 18750, "AG" : 30000, "LR" : 125000, "MHR" : 5400, "HR" : 3500, "LC" : 3500, "GC" : 12500,
					"GCR" : 12500, "LI-R" : 120000, "GI-R" : 250000, "IC" : 40000, "LI" : 120000, "OS" : 0} 

	oldmans_codes = {'AR' : 87120, 'R' : 43560, 'C' : 43560, 'VR' : 10000, 'VC' : 10000, 'I' : 130680,
					 'CI' : 130680, 'IPRA' : 130680, 'P' : 0}

	fields = arcpy.ListFields(zoningData)
	if 'MINLOT' not in fields:
		arcpy.AddField_management(zoningData, 'MINLOT', 'DOUBLE')
	if 'RESDENSITY' not in fields:
		arcpy.AddField_management(zoningData, 'RESDENSITY', 'DOUBLE')
	
	cursor = arcpy.UpdateCursor(zoningData)
	
	if 'CARNEY' in zoningData or 'CP' in zoningData:
		for row in cursor:
			for code, size in carney_codes.iteritems():
				if code == row.getValue('Zone_ID'):
					row.setValue('MINLOT', size)
					
					# not preserved land
					if size != 0:
						row.setValue('RESDENSITY', size ** (-1))
						
					# preserved land
					else:
						row.setValue('RESDENSITY', size)
					cursor.updateRow(row)
		del row, cursor
	
	elif 'HOPEWELL' in zoningData:
		for row in cursor: 
			size = row.getValue('MINLOT')
			if size != 0:
				row.setValue('RESDENSITY', row.getValue('MINLOT') ** (-1))
			else:
				row.setValue('RESDENSITY', size)
			cursor.updateRow(row)
		del row, cursor
	
	elif 'OLDMAN' in zoningData:
		for row in cursor:
			for code, size in oldmans_codes.iteritems():
				if code == row.getValue('Zone_ID'):
					row.setValue('MINLOT', size)
					if size != 0:
						row.setValue('RESDENSITY', size ** (-1))
					else:
						row.setValue('RESDENSITY', size)
					cursor.updateRow(row)
		del row, cursor
	
	currentFile = arcpy.CopyFeatures_management(zoningData, outputWorkspace + '\\muni_minLotCopy')
	return currentFile

# Cleans up the fields for the final output file
def uglyFieldManagement(fc):
	fields = [field.name for field in arcpy.ListFields(fc)]
	for f in fields:
		if 'FID' in f or '_1' in f:
			arcpy.DeleteField_management(fc, f)

# The following three methods correspond to the calculation of buildout numbers for both current zoning and Nitrate 
# dilution standards. 

def nitrate_BO(minLot, septicDensity, shapeArea, isSeptic, CZ_BO_number):
	# converting from acres to sq. feet
	septicDensitySqFt = septicDensity * 43560
	canSplit = False
	
	if isSeptic:
		# remaining parcel area is 2x the size of the minimum lot requirement
		# as well as the septic density requirement
		if shapeArea > (minLot * 2) and shapeArea > (septicDensitySqFt * 2) and minLot != 0:
			canSplit = True
		
		# if the parcel can be split, return the number of lots that can be
		# created, rounded down. if not, return null.
		if canSplit:
			return math.floor(shapeArea / septicDensitySqFt)
			
		else:
			# Cannot be split, only 1 unit allowed
			return 0
	
	# Sewer areas, return the current zoning buildout number
	else:
		return CZ_BO_number
	
	
def currentZoning_BO(minLot, shapeArea):
	# Preserved lands, cannot be split
	if minLot == 0:
		return 0
	elif (minLot * 2) < shapeArea:
		return math.floor(shapeArea / minLot)
	else:
		# Cannot be split, only 1 unit allowed
		return 0
		

def canSplit(NO3_val, CZ_val):
	if NO3_val + CZ_val > 1:
		return 1
	else:
		return 0

####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
# The following code is the overall model. The output generated here is what should be displayed in City Engine

arcpy.env.overwriteOutput = True
zoning = arcpy.GetParameterAsText(0)
muniName = arcpy.GetParameterAsText(1)
outputWorkspace = arcpy.GetParameterAsText(2)

arcpy.env.workspace = 'R:\\Salem\\model_inputs.gdb'
deleteFiles = []

inputs = ['nhd_waterbodies', 'NO3_densities',  'openspace_county', 'openspace_state',  'parcels',  'preserved_farms', 
		  'swqs',  'water_purveyors',  'wetlands', 'Land_Use_Land_Cover_2012', 'sewer_service_area']

# Clip inputs to the municipality area
arcpy.AddMessage('Clipping Inputs...')	  
for file in inputs:
	deleteFiles.append(arcpy.Clip_analysis(file, zoning, outputWorkspace + '\\muni_' + file))

arcpy.env.workspace = outputWorkspace
	
wetlands = 'muni_wetlands'
parcels = 'muni_parcels'
waterbodies = 'muni_nhd_waterbodies'
NO3_densities = 'muni_NO3_densities'
OS_State = 'muni_openspace_state'
OS_County = 'muni_openspace_county'
swqs = 'muni_swqs'
landUse = 'muni_Land_Use_Land_Cover_2012'
farms = 'muni_preserved_farms'
sewer_area = 'muni_sewer_service_area'

# Calculate minimum lot size values for the individual zones
arcpy.AddMessage('Calculating minimum lot sizes...')
zoning = minimumLotSize(zoning, arcpy.GetParameterAsText(2))
deleteFiles.append(zoning)

# Selecting zoned open space (may differ from other OS)
zoned_OS = arcpy.Select_analysis(zoning, 'muni_zoned_OS', '\"MINLOT\" = 0')
deleteFiles.append(zoned_OS)

# Create zoning by parcels
arcpy.AddMessage('Appending zoning data...')
currentFile = arcpy.Identity_analysis(zoning, parcels, 'muni_zoning_by_parcels')
deleteFiles.append(currentFile)

# Delete areas that are coincident with streets
arcpy.SelectLayerByAttribute_management(arcpy.MakeFeatureLayer_management(currentFile, 'zone_lyr'), 'NEW_SELECTION',
										'\"FID_muni_parcels\" = -1')
arcpy.DeleteFeatures_management('zone_lyr')

# Creating the Surface Water Antideg. buffers
arcpy.SelectLayerByAttribute_management(arcpy.MakeFeatureLayer_management(swqs, 'swqs_lyr'), 'NEW_SELECTION', '\"ANTIDEG\" = \'C1\'')
c1_buffers = arcpy.Buffer_analysis('swqs_lyr', 'muni_C1_buffer', '300 Feet')
arcpy.SelectLayerByAttribute_management('swqs_lyr', 'NEW_SELECTION', '\"ANTIDEG\" = \'C2\'')
c2_buffers = arcpy.Buffer_analysis('swqs_lyr', 'muni_C2_buffer', '50 Feet')
deleteFiles.append(c1_buffers)
deleteFiles.append(c2_buffers)

# Creating the Urban land use layer
urban_lu = arcpy.Select_analysis(landUse, 'muni_urban_lu', '\"TYPE12\" = \'URBAN\'')
deleteFiles.append(urban_lu)

# Creating the constraints layer and erasing the constraints
constraintsFiles = [urban_lu, c1_buffers, c2_buffers, wetlands, waterbodies, OS_State, OS_County, zoned_OS, farms]
constraints = arcpy.Merge_management(constraintsFiles, 'muni_constraints')
currentFile = arcpy.Erase_analysis(currentFile, constraints, 'muni_constraints_erased')
deleteFiles.append(constraints)
deleteFiles.append(currentFile)

# Taking out anything that doesn't meet minimum lot size
currentFile = arcpy.Select_analysis(currentFile, 'muni_minimumLot_met', '\"Shape_Area\" >= \"MINLOT\"')
deleteFiles.append(currentFile)

# Append the sewer service data
arcpy.AddMessage('Identifying sewer and septic areas...')
currentFile = arcpy.Identity_analysis(currentFile, sewer_area, 'muni_sewer_service_ID')
deleteFiles.append(currentFile)
arcpy.AddField_management(currentFile, 'SYSTEM', 'TEXT')

cursor = arcpy.UpdateCursor(currentFile)
for row in cursor:
	if row.getValue('FID_muni_sewer_service_area') == -1:
		row.setValue('SYSTEM', 'SEPTIC')
	else:
		row.setValue('SYSTEM', 'SEWER')
	cursor.updateRow(row)
del row, cursor 

# Append the Nitrate Dilution watershed data
currentFile = arcpy.Identity_analysis(currentFile, NO3_densities, 'muni_appended_NO3_densities')
deleteFiles.append(currentFile) 

# Delete any geometry that doesn't line up
arcpy.MakeFeatureLayer_management(currentFile, 'lyr')
arcpy.SelectLayerByAttribute_management('lyr', 'NEW_SELECTION', '\"FID_muni_NO3_densities\" = -1')
arcpy.DeleteFeatures_management('lyr')

# Cleaning up ugly fields
uglyFieldManagement(currentFile)

# Calculate the buildout numbers, post-constraint erase
arcpy.AddField_management(currentFile, 'CZ_BLDOUT', 'LONG')
arcpy.AddField_management(currentFile, 'NO3_BLDOUT', 'LONG')

arcpy.AddMessage('Calculating buildout values...')
cursor = arcpy.UpdateCursor(currentFile)
for row in cursor: 

	system = row.getValue('SYSTEM')
	isSeptic = False
	if system == 'SEPTIC':
		isSeptic = True
	
	sepdens = row.getValue('SEPDENS')
	minLot = row.getValue('MINLOT')
	area = row.getValue('Shape_Area')
	cz_BO = currentZoning_BO(minLot, area)
	NO3_BO = nitrate_BO(minLot, sepdens, area, isSeptic, cz_BO)

	row.setValue('CZ_BLDOUT', cz_BO)
	row.setValue('NO3_BLDOUT', NO3_BO)
	
	cursor.updateRow(row)
del row, cursor

# Finding parcels that are contained in both sewer and septic areas. Those that do will be assigned a 
# 'SEWER/SEPTIC' value in the "SYSTEM" field, allowing for a clean dissolve on pams pin. 
arcpy.AddMessage('Finding multi-system parcels...')
arcpy.MakeFeatureLayer_management(currentFile, 'pams_lyr')
cursor = arcpy.UpdateCursor('pams_lyr')
for row in cursor:
	if row.getValue('SYSTEM') != 'SEWER/SEPTIC':
		pams_pin = row.getValue('PAMS_PIN')
		arcpy.SelectLayerByAttribute_management('pams_lyr', 'NEW_SELECTION', '\"PAMS_PIN\" = \'%s\''%(pams_pin))
		sysSet = set()
		subCursor = arcpy.SearchCursor('pams_lyr')
		for subRow in subCursor:
			sysSet.add(subRow.getValue('SYSTEM'))
		del subRow, subCursor
		if len(sysSet) > 1:
			arcpy.CalculateField_management('pams_lyr', 'SYSTEM', '\'SEWER/SEPTIC\'', 'PYTHON_9.3')
		arcpy.SelectLayerByAttribute_management('pams_lyr', 'CLEAR_SELECTION')
	cursor.updateRow(row)
del row, cursor

# Dissolve parts of parcels on pams pin									             #Dissolve fields
currentFile = arcpy.Dissolve_management(currentFile, 'muni_result_combined', ['PAMS_PIN', 'Zone_ID', 'SYSTEM'], 
										[['CZ_BLDOUT', 'SUM'], ['NO3_BLDOUT', 'SUM']])
											#Statistics fields


arcpy.AddField_management(currentFile, 'CANSPLIT', 'SHORT')
arcpy.AddField_management(currentFile, 'NO3_BLDOUT', 'LONG')
arcpy.AddField_management(currentFile, 'CZ_BLDOUT', 'LONG')

cursor = arcpy.UpdateCursor(currentFile)
for row in cursor:
	row.setValue('NO3_BLDOUT', row.getValue('SUM_NO3_BLDOUT'))
	row.setValue('CZ_BLDOUT', row.getValue('SUM_CZ_BLDOUT'))
	row.setValue('CANSPLIT', canSplit(row.getValue('NO3_BLDOUT'), row.getValue('CZ_BLDOUT')))
	cursor.updateRow(row)
del row, cursor

arcpy.DeleteField_management(currentFile, 'SUM_NO3_BLDOUT')
arcpy.DeleteField_management(currentFile, 'SUM_CZ_BLDOUT')

# Rename the final file
currentFile = arcpy.Rename_management(currentFile, '%s_final_result'%(muniName))

# Change the 0's to 1's for the buildout numbers
cursor = arcpy.UpdateCursor(currentFile)
for row in cursor:
	if row.getValue('NO3_BLDOUT') == 0:
		row.setValue('NO3_BLDOUT', 1)
	if row.getValue('CZ_BLDOUT') == 0:
		row.setValue('CZ_BLDOUT', 1)
	cursor.updateRow(row)
del row, cursor

# Thinness ratio
arcpy.AddField_management(currentFile, 'THINNESS', 'DOUBLE')
arcpy.CalculateField_management(currentFile, 'THINNESS', '4 * math.pi * !Shape_Area!/(!Shape_Length ** (2))', 'PYTHON_9.3')

# Deleting temp files
for file in deleteFiles:
	arcpy.Delete_management(file)
































