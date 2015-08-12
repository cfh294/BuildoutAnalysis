#!/usr/bin/python
####################################################################################################################################
# NJ Zoning Buildout Analysis
# Code by Connor Hornibrook
# Rowan University
# Lastest Update - 13 July 2015
#
# ArcMap script parameters (in this order):
#       Zoning - Required Feature Class
#       Municipality Name - Required String
#       Additional Constraints - Optional Multivalue Feature Class 
#       Output Location - Required Workspace
####################################################################################################################################

import arcpy, math, sets

####################################################################################################################################
# Methods
####################################################################################################################################

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

### Cleans up the fields for the final output file
##def uglyFieldManagement(fc):
##	fields = [field.name for field in arcpy.ListFields(fc)]
##	for f in fields:
##		if 'FID' in f or '_1' in f:
##			arcpy.DeleteField_management(fc, f)

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
	
# Calculate the buildout numbers
def buildoutCalculations(featureClass, isPost):
        field_names = [f.name for f in arcpy.ListFields(featureClass)]
        NO3_field = ''
        CZ_field = ''
        if isPost:    
                if'CZBO_POST' not in field_names:
                        arcpy.AddField_management(featureClass, 'CZBO_POST', 'LONG', '', '', '', 'CZ Buildout Post-const. Erase')
                        CZ_field = 'CZBO_POST'
                if'NO3BO_POST' not in field_names:
                        arcpy.AddField_management(featureClass, 'NO3BO_POST', 'LONG', '', '', '', 'NO3 Buildout Post-const. Erase')
                        NO3_field = 'NO3BO_POST'
                        
        else:
                if'CZBO_PRE' not in field_names:
                        arcpy.AddField_management(featureClass, 'CZBO_PRE', 'LONG', '', '', '', 'CZ Buildout Pre-const. Erase')
                        CZ_field = 'CZBO_PRE'
                if'NO3BO_PRE' not in field_names:
                        arcpy.AddField_management(featureClass, 'NO3BO_PRE', 'LONG', '', '', '', 'NO3 Buildout Pre-const. Erase')
                        NO3_field = 'NO3BO_PRE'

        arcpy.AddMessage('Calculating buildout values...')
        cursor = arcpy.UpdateCursor(featureClass)
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

                row.setValue(CZ_field, cz_BO)
                row.setValue(NO3_field, NO3_BO)
                
                cursor.updateRow(row)
        del row, cursor

####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
# The following code is the overall model. The output generated here is what should be displayed in City Engine

arcpy.env.overwriteOutput = True
zoning = arcpy.GetParameterAsText(0)
muniName = arcpy.GetParameterAsText(1)
outputWorkspace = arcpy.GetParameterAsText(3)

# An array that will contain all temp files that will be deleted at the very end
deleteFiles = []

# Merge the additional constraints
add_constraints = ''
if arcpy.GetParameterAsText(2):
        arcpy.AddMessage('Clipping Optional Constraints...')
        add_const_paths = []
        count = 1
        for constraint in arcpy.GetParameterAsText(2).split(';'):
                file_name = 'muni_op_constraint_%s'%(count)
                add_const_paths.append(arcpy.Clip_analysis(constraint, zoning, file_name))
                deleteFiles.append(file_name)
                count += 1
        add_constraints = arcpy.Merge_management(add_const_paths, 'muni_add_const')
        deleteFiles.append(add_constraints)
                

arcpy.env.workspace = 'R:\\Salem\\model_inputs.gdb'

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
wp = 'muni_water_purveyors'

# Calculate minimum lot size values for the individual zones
arcpy.AddMessage('Calculating minimum lot sizes...')
zoning = minimumLotSize(zoning, arcpy.GetParameterAsText(3))
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

# Append the sewer service data
arcpy.AddMessage('Identifying sewer and septic areas...')
currentFile = arcpy.Identity_analysis(currentFile, sewer_area, 'muni_sewer_service_ID')
deleteFiles.append(currentFile)
field_names = [f.name for f in arcpy.ListFields(currentFile)]
if 'SYSTEM' not in field_names:
        arcpy.AddField_management(currentFile, 'SYSTEM', 'TEXT')

cursor = arcpy.UpdateCursor(currentFile)
for row in cursor:
	if row.getValue('FID_muni_sewer_service_area') == -1:
		row.setValue('SYSTEM', 'SEPTIC')
	else:
		row.setValue('SYSTEM', 'SEWER')
	cursor.updateRow(row)
del row, cursor

# Getting field names
field_names = [f.name for f in arcpy.ListFields(currentFile)]

# Append the Nitrate Dilution watershed data
currentFile = arcpy.Identity_analysis(currentFile, NO3_densities, 'muni_appended_NO3_densities')
deleteFiles.append(currentFile) 

# Delete any geometry that doesn't line up
arcpy.MakeFeatureLayer_management(currentFile, 'lyr')
arcpy.SelectLayerByAttribute_management('lyr', 'NEW_SELECTION', '\"FID_muni_NO3_densities\" = -1')
arcpy.DeleteFeatures_management('lyr')

# Calculate buildout for pre-constraint erasure areas
buildoutCalculations(currentFile, False)

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
if add_constraints != '':
        constraintsFiles.append(add_constraints) # optional constraints
constraints = arcpy.Merge_management(constraintsFiles, 'muni_constraints')
currentFile = arcpy.Erase_analysis(currentFile, constraints, 'muni_constraints_erased')
deleteFiles.append(constraints)
deleteFiles.append(currentFile)

# Taking out anything that doesn't meet minimum lot size
currentFile = arcpy.Select_analysis(currentFile, 'muni_minimumLot_met', '\"Shape_Area\" >= \"MINLOT\"')
deleteFiles.append(currentFile)

# Cleaning up ugly fields
#uglyFieldManagement(currentFile)

# Calculate buildout for post-constraint erasure areas
buildoutCalculations(currentFile, True)

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

# Dissolve parts of parcels on pams pin, sum the buildout numbers								        
currentFile = arcpy.Dissolve_management(currentFile, 'muni_result_combined', ['PAMS_PIN', 'Zone_ID', 'SYSTEM'], [['CZBO_POST', 'SUM'], ['NO3BO_POST', 'SUM'], ['CZBO_PRE', 'SUM'], ['NO3BO_PRE', 'SUM']])
deleteFiles.append(currentFile)

arcpy.AddField_management(currentFile, 'CANSP_PRE', 'SHORT', '', '', '', 'Can Split Pre-const. Erase')
arcpy.AddField_management(currentFile, 'CANSP_POST', 'SHORT', '', '', '', 'Can Split Post-const. Erase')
arcpy.AddField_management(currentFile, 'NO3BO_PRE', 'LONG', '', '', '', 'NO3 Buildout Pre-const. Erase')
arcpy.AddField_management(currentFile, 'NO3BO_POST', 'LONG', '', '', '', 'NO3 Buildout Post-const. Erase')
arcpy.AddField_management(currentFile, 'CZBO_PRE', 'LONG', '', '', '', 'Current Zoning Buildout Pre-const. Erase')
arcpy.AddField_management(currentFile, 'CZBO_POST', 'LONG', '', '', '', 'Current Zoning Buildout Post-const. Erase')

cursor = arcpy.UpdateCursor(currentFile)
for row in cursor:
	row.setValue('NO3BO_POST', row.getValue('SUM_NO3BO_POST'))
	row.setValue('NO3BO_PRE', row.getValue('SUM_NO3BO_PRE'))
	row.setValue('CZBO_POST', row.getValue('SUM_CZBO_POST'))
	row.setValue('CZBO_PRE', row.getValue('SUM_CZBO_PRE'))
	row.setValue('CANSP_PRE', canSplit(row.getValue('NO3BO_PRE'), row.getValue('CZBO_PRE')))
	row.setValue('CANSP_POST', canSplit(row.getValue('NO3BO_POST'), row.getValue('CZBO_POST')))
	cursor.updateRow(row)
del row, cursor

arcpy.DeleteField_management(currentFile, 'SUM_CZBO_POST')
arcpy.DeleteField_management(currentFile, 'SUM_CZBO_PRE')
arcpy.DeleteField_management(currentFile, 'SUM_NO3BO_POST')
arcpy.DeleteField_management(currentFile, 'SUM_NO3BO_PRE')

# Change the 0's to 1's for the buildout numbers
cursor = arcpy.UpdateCursor(currentFile)
for row in cursor:
	if row.getValue('CZBO_PRE') == 0:
		row.setValue('CZBO_PRE', 1)
	if row.getValue('CZBO_POST') == 0:
		row.setValue('CZBO_POST', 1)
	if row.getValue('NO3BO_PRE') == 0:
		row.setValue('NO3BO_PRE', 1)
	if row.getValue('NO3BO_POST') == 0:
		row.setValue('NO3BO_POST', 1)
	
	cursor.updateRow(row)
del row, cursor

# Appending water purveyor and watershed data
currentFile = arcpy.Identity_analysis(currentFile, wp, 'muni_appended_wps')
deleteFiles.append(currentFile)
currentFile = arcpy.Identity_analysis(currentFile, NO3_densities, 'muni_appended_wsheds')
deleteFiles.append(currentFile)


# Doing some ugly fields management for the appended data
goodFields = ['OBJECTID', 'Shape', 'Shape_Area', 'Shape_Length', 'HUC11', 'W_NAME', 'SEPDENS', 'AVGRECHRG', 'PURVNAME']
fields = [field.name for field in arcpy.ListFields(wp)] # water purveyor fields
fields.extend([field.name for field in arcpy.ListFields(NO3_densities)]) # watershed fields

for f in fields:
        if f not in goodFields:
                arcpy.DeleteField_management(currentFile, f)
                
fields = [field.name for field in arcpy.ListFields(currentFile)]

for f in fields: # deleting other ugly fields
        if 'FID' in f or '_1' in f:
                arcpy.DeleteField_management(currentFile, f)

# Thinness ratio
arcpy.AddField_management(currentFile, 'THINNESS', 'DOUBLE')
arcpy.CalculateField_management(currentFile, 'THINNESS', '4 * math.pi * !Shape_Area!/(!Shape_Length! ** (2))', 'PYTHON_9.3')

# Rename the final file
currentFile = arcpy.Rename_management(currentFile, '%s_final_result'%(muniName))

# Deleting temp files
arcpy.AddMessage('Deleting temp files...')
for file in deleteFiles:
	arcpy.Delete_management(file)
































