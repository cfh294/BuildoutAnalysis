#!/usr/bin/env python
################################################################################
# Model - Estimated buildout as points, based on geography and current zoning
# Code by Connor Hornibrook
#
# Description:
#   Arcpy tool for producing buildout points for a municipality based on
# zoning minimum lot size standards. This model is a more visual alternative
# to the NJDEP buildout estimation model.
#
# Input system parameters:
#   sys.argv[1] = zoning GIS data for the town
#   sys.argv[2] = the desired name modifier for the output file
#   sys.argv[3] = the output workspace
################################################################################

# libraries and constants
import arcpy, math, sets, random, sys
MINLOT_ROW_INDEX = 2 # used for modifying point geoms. 
WIGGLE_FACTOR = .2 # the amount of simulated natural movement for the
                   # generated points, .2 or lower is recommended

def stripDash(string):
    newString = ''
    if '-' in string:
        parts = string.split('-')
        for part in parts:
            newString += part
        return newString

    # no dashes found, return original input
    else:
        return string
        
if __name__ == '__main__':
    # Output workspace and input system params. 
    zoning = arcpy.Dissolve_management(sys.argv[1], 'dissolved_zoning', ['Zone_ID', 'MINLOT'])
    outFileName = sys.argv[2]
    arcpy.env.workspace = sys.argv[3] 
    arcpy.env.overwriteOutput = True

    # global variables
    prj = arcpy.Describe(zoning).spatialReference
    
    # Grabbing the name of the shape field from the zoning data
    shapeFieldName = arcpy.Describe(zoning).shapeFieldName
    points = [] # contains all point files that are to be created
    clips = [] # contains all clipped point files
    arcpy.AddMessage('Creating zone fishnets...')

    # Calculating the fishnets
    cur = arcpy.SearchCursor(zoning)
    for row in cur:
        minLot = row.getValue('MINLOT')
        if minLot > 0: # some preserved zones are marked with a 0 for minimum lot size in our data
            zoneText = stripDash(row.getValue('Zone_ID'))
            arcpy.AddMessage(zoneText)

            # Grabbing the needed information to create zone-specific fishnets. 
            extent = row.getValue(shapeFieldName).extent
            origin = str(extent.lowerLeft)
            upperRight = str(extent.upperRight)
            yax = str(extent.XMin) + ' ' + str(extent.YMax + 10)

            val = math.sqrt(minLot)

            # Create and delete a fishnet for this zone. It is getting deleted because
            # the generated label points file is the only needed file.
            arcpy.Delete_management(arcpy.CreateFishnet_management('net_%s'%(zoneText), origin,
                                                                   yax, val, val, 0, 0, upperRight,
                                                                   'LABELS', zoning, 'POLYLINE'))
            
            points.append('net_%s_label'%(zoneText)) # add it to the list of points files
    del row, cur
                
    # clipping fishnets to the bounds of the zones
    arcpy.MakeFeatureLayer_management(zoning, 'zlyr')
    cur = arcpy.SearchCursor(zoning)
    arcpy.AddMessage('Creating clipped nets...')
    for row in cur:
        minLot = row.getValue('MINLOT')
        
        if minLot != 0:
            zoneID = row.getValue('Zone_ID')
            zoneText = stripDash(zoneID)
            arcpy.SelectLayerByAttribute_management('zlyr', 'NEW_SELECTION', '"Zone_ID" = \'%s\''%(zoneID))
            clips.append(arcpy.Clip_analysis('net_%s_label'%(zoneText), 'zlyr', 'fishnet_%s'%(zoneText)))   
    del row, cur

    # Merging the clipped points
    arcpy.AddMessage('Merging fishnets...')
    arcpy.Merge_management(clips, 'fishnet_points_merged')

    # Deleting all of the temp files
    arcpy.AddMessage('Deleting temp files...')
    for fc in clips:
        arcpy.Delete_management(fc)
    for fc in points:
        arcpy.Delete_management(fc)

    # Appending the original zoning data
    fileName = '%s_FISHNET'%(outFileName)
    arcpy.Identity_analysis('fishnet_points_merged', zoning, fileName)
    arcpy.Delete_management('fishnet_points_merged')
    arcpy.Delete_management(zoning) 

    # Moving the points based on WIGGLE_FACTOR
    arcpy.AddMessage('Offsetting points...')
    with arcpy.da.UpdateCursor(fileName, ["SHAPE@X", "SHAPE@Y", "MINLOT"]) as cursor:
        for row in cursor:
            offset = WIGGLE_FACTOR * math.sqrt(row[MINLOT_ROW_INDEX])
            # setting the x and y offets using random number generation
            xOff = 0
            yOff = 0
            randInt = random.randrange(2)
            if randInt > 0:
                xOff += random.uniform(0, offset)
            else:
                xOff -= random.uniform(0, offset)
                
            randInt = random.randrange(2)
            if randInt > 0:
                yOff += random.uniform(0, offset)
            else:
                yOff -= random.uniform(0, offset)

            row[0] = row[0] + xOff
            row[1] = row[1] + yOff

            
            try:
                cursor.updateRow(row) # update the geometry
            except(TypeError):
                arcpy.AddMessage('STILL MESSED UP')

    arcpy.DefineProjection_management(fileName, prj) # setting the projection to that of the zoning data
                


    
    
    
