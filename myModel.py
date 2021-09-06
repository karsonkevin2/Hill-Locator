"""
Model exported as python.
Name : My Model
Group : 
With QGIS : 32002
"""

from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterNumber
from qgis.core import QgsProcessingParameterRasterLayer
from qgis.core import QgsProcessingParameterCrs
from qgis.core import QgsProcessingParameterBoolean
from qgis.core import QgsProcessingParameterDistance
from qgis.core import QgsProcessingParameterField
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterFeatureSink
from qgis.core import QgsProcessingParameterDefinition
from qgis.core import QgsExpression
import processing


class MyModel(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        param = QgsProcessingParameterNumber('Bufferscale', 'Buffer scale', type=QgsProcessingParameterNumber.Double, minValue=0, maxValue=1, defaultValue=0.999)
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)
        self.addParameter(QgsProcessingParameterRasterLayer('DigitalElevationModel', 'Digital Elevation Model', defaultValue=None))
        self.addParameter(QgsProcessingParameterCrs('Projection', 'Projection', defaultValue='EPSG:26976'))
        param = QgsProcessingParameterBoolean('RemoveShortSegments', 'Remove Short Segments', defaultValue=True)
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)
        param = QgsProcessingParameterBoolean('UseBuffer', 'Use Buffer?', defaultValue=True)
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)
        param = QgsProcessingParameterDistance('densifiedseparation', 'Densified Separation', parentParameterName='roads', minValue=0, defaultValue=5)
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)
        self.addParameter(QgsProcessingParameterNumber('minimumgrade', 'Minimum Grade', type=QgsProcessingParameterNumber.Double, minValue=0, defaultValue=2.5))
        self.addParameter(QgsProcessingParameterField('roadname', 'Road Name', type=QgsProcessingParameterField.Any, parentLayerParameterName='roads', allowMultiple=False, defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('roads', 'Roads', types=[QgsProcessing.TypeVectorLine], defaultValue=None))
        param = QgsProcessingParameterDistance('segmentlengths', 'Segment Lengths', parentParameterName='roads', minValue=0, defaultValue=50)
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)
        self.addParameter(QgsProcessingParameterFeatureSink('Hills', 'Hills', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, supportsAppend=True, defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(24, model_feedback)
        results = {}
        outputs = {}

        # Tile index
        alg_params = {
            'ABSOLUTE_PATH': False,
            'CRS_FIELD_NAME': '',
            'CRS_FORMAT': 0,  # Auto
            'LAYERS': parameters['DigitalElevationModel'],
            'PATH_FIELD_NAME': 'location',
            'PROJ_DIFFERENCE': False,
            'TARGET_CRS': None,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['TileIndex'] = processing.run('gdal:tileindex', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # Reproject reference
        alg_params = {
            'INPUT': outputs['TileIndex']['OUTPUT'],
            'OPERATION': '',
            'TARGET_CRS': parameters['Projection'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ReprojectReference'] = processing.run('native:reprojectlayer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        # Affine transform
        alg_params = {
            'DELTA_M': 0,
            'DELTA_X': QgsExpression('IF( @UseBuffer =TRUE, (1- @Bufferscale) *( @Reproject_reference_OUTPUT_maxx +  @Reproject_reference_OUTPUT_minx  )/2, 0)').evaluate(),
            'DELTA_Y': QgsExpression('IF( @UseBuffer =TRUE, (1- @Bufferscale) *( @Reproject_reference_OUTPUT_maxy +  @Reproject_reference_OUTPUT_miny  )/2, 0)').evaluate(),
            'DELTA_Z': 0,
            'INPUT': outputs['ReprojectReference']['OUTPUT'],
            'ROTATION_Z': 0,
            'SCALE_M': 1,
            'SCALE_X': QgsExpression('IF( @UseBuffer =TRUE,  @Bufferscale , 1)').evaluate(),
            'SCALE_Y': QgsExpression('IF( @UseBuffer =TRUE,  @Bufferscale , 1)').evaluate(),
            'SCALE_Z': 1,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['AffineTransform'] = processing.run('native:affinetransform', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}

        # Clip
        alg_params = {
            'INPUT': parameters['roads'],
            'OVERLAY': outputs['AffineTransform']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Clip'] = processing.run('native:clip', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(4)
        if feedback.isCanceled():
            return {}

        # Reproject layer
        alg_params = {
            'INPUT': outputs['Clip']['OUTPUT'],
            'OPERATION': '',
            'TARGET_CRS': parameters['Projection'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ReprojectLayer'] = processing.run('native:reprojectlayer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(5)
        if feedback.isCanceled():
            return {}

        # Dissolve same roads
        alg_params = {
            'FIELD': parameters['roadname'],
            'INPUT': outputs['ReprojectLayer']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['DissolveSameRoads'] = processing.run('native:dissolve', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(6)
        if feedback.isCanceled():
            return {}

        # Chop up roads
        alg_params = {
            'INPUT': outputs['DissolveSameRoads']['OUTPUT'],
            'LENGTH': parameters['segmentlengths'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ChopUpRoads'] = processing.run('native:splitlinesbylength', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(7)
        if feedback.isCanceled():
            return {}

        # Add extra nodes
        alg_params = {
            'INPUT': outputs['ChopUpRoads']['OUTPUT'],
            'INTERVAL': parameters['densifiedseparation'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['AddExtraNodes'] = processing.run('native:densifygeometriesgivenaninterval', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(8)
        if feedback.isCanceled():
            return {}

        # Drape elevation
        alg_params = {
            'BAND': 1,
            'INPUT': outputs['AddExtraNodes']['OUTPUT'],
            'NODATA': 0,
            'RASTER': parameters['DigitalElevationModel'],
            'SCALE': 1,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['DrapeElevation'] = processing.run('native:setzfromraster', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(9)
        if feedback.isCanceled():
            return {}

        # Climb along segments
        alg_params = {
            'INPUT': outputs['DrapeElevation']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ClimbAlongSegments'] = processing.run('qgis:climbalongline', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(10)
        if feedback.isCanceled():
            return {}

        # Get length segments
        alg_params = {
            'FIELD_LENGTH': 50000,
            'FIELD_NAME': 'len1',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 1,  # Integer
            'FORMULA': '$length',
            'INPUT': outputs['ClimbAlongSegments']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['GetLengthSegments'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(11)
        if feedback.isCanceled():
            return {}

        # Get grade segments
        alg_params = {
            'FIELD_LENGTH': 10,
            'FIELD_NAME': 'grade_net',
            'FIELD_PRECISION': 7,
            'FIELD_TYPE': 0,  # Float
            'FORMULA': 'abs(attribute(\'climb\') - attribute(\'descent\')) / attribute(\'len1\')',
            'INPUT': outputs['GetLengthSegments']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['GetGradeSegments'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(12)
        if feedback.isCanceled():
            return {}

        # Threshold grade
        alg_params = {
            'INPUT': outputs['GetGradeSegments']['OUTPUT'],
            'OUTPUT_Thresholded Segments': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ThresholdGrade'] = processing.run('native:filter', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(13)
        if feedback.isCanceled():
            return {}

        # Mark direction
        alg_params = {
            'FIELD_LENGTH': 1,
            'FIELD_NAME': 'direction',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 1,  # Integer
            'FORMULA': 'if(attribute(\'climb\') > attribute(\'descent\'), 1, 0)',
            'INPUT': outputs['ThresholdGrade']['OUTPUT_Thresholded Segments'],
            'NEW_FIELD': True,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['MarkDirection'] = processing.run('qgis:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(14)
        if feedback.isCanceled():
            return {}

        # Duplicate name
        alg_params = {
            'FIELD_LENGTH': 50,
            'FIELD_NAME': 'name',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 2,  # String
            'FORMULA': 'attribute(@roadname)',
            'INPUT': outputs['MarkDirection']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['DuplicateName'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(15)
        if feedback.isCanceled():
            return {}

        # Dissolve hills
        alg_params = {
            'FIELD': ['direction','name'],
            'INPUT': outputs['DuplicateName']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['DissolveHills'] = processing.run('native:dissolve', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(16)
        if feedback.isCanceled():
            return {}

        # Drop field(s)
        alg_params = {
            'COLUMN': ['climb','descent','minelev','maxelev','len1'],
            'INPUT': outputs['DissolveHills']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['DropFields'] = processing.run('native:deletecolumn', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(17)
        if feedback.isCanceled():
            return {}

        # Reseperate
        alg_params = {
            'INPUT': outputs['DropFields']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Reseperate'] = processing.run('native:multiparttosingleparts', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(18)
        if feedback.isCanceled():
            return {}

        # Climb hills
        alg_params = {
            'INPUT': outputs['Reseperate']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ClimbHills'] = processing.run('qgis:climbalongline', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(19)
        if feedback.isCanceled():
            return {}

        # Get length
        alg_params = {
            'FIELD_LENGTH': 10,
            'FIELD_NAME': 'length',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 1,  # Integer
            'FORMULA': '$length',
            'INPUT': outputs['ClimbHills']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['GetLength'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(20)
        if feedback.isCanceled():
            return {}

        # Filter Shorts
        alg_params = {
            'INPUT': outputs['GetLength']['OUTPUT'],
            'OUTPUT_': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['FilterShorts'] = processing.run('native:filter', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(21)
        if feedback.isCanceled():
            return {}

        # Get height
        alg_params = {
            'FIELD_LENGTH': 10,
            'FIELD_NAME': 'height',
            'FIELD_PRECISION': 3,
            'FIELD_TYPE': 0,  # Float
            'FORMULA': 'abs(attribute(\'climb\')-attribute(\'descent\'))',
            'INPUT': outputs['FilterShorts']['OUTPUT_'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['GetHeight'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(22)
        if feedback.isCanceled():
            return {}

        # Get grade
        alg_params = {
            'FIELD_LENGTH': 10,
            'FIELD_NAME': 'grade_net',
            'FIELD_PRECISION': 7,
            'FIELD_TYPE': 0,  # Float
            'FORMULA': 'abs(attribute(\'climb\') - attribute(\'descent\')) / attribute(\'length\')',
            'INPUT': outputs['GetHeight']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['GetGrade'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(23)
        if feedback.isCanceled():
            return {}

        # Field calculator
        alg_params = {
            'FIELD_LENGTH': 7,
            'FIELD_NAME': 'CAT',
            'FIELD_PRECISION': 5,
            'FIELD_TYPE': 0,  # Float
            'FORMULA': 'attribute(\'grade_net\') * attribute(\'height\')',
            'INPUT': outputs['GetGrade']['OUTPUT'],
            'OUTPUT': parameters['Hills']
        }
        outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Hills'] = outputs['FieldCalculator']['OUTPUT']
        return results

    def name(self):
        return 'My Model'

    def displayName(self):
        return 'My Model'

    def group(self):
        return ''

    def groupId(self):
        return ''

    def createInstance(self):
        return MyModel()
