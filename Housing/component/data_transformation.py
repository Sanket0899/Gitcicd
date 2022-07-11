
from sklearn import preprocessing
from Housing.logger import logging
from Housing.exception import HousingException
import sys,os
import pandas as pd
import numpy as np
from Housing.entity.config_entity import DataIngestionConfig,DataTransformationConfig,DataValidationConfig
from Housing.entity.artifact_entity import DataIngestionArtifact,DataValidationArtifact,DataTransformationArtifact
from sklearn.base import BaseEstimator,TransformerMixin
from Housing.constant import *
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler,OneHotEncoder
from sklearn.impute import SimpleImputer
from Housing.util.util import read_yaml_file,save_object,save_numpy_array_data,load_data

class FeatureGenerator(BaseEstimator, TransformerMixin):

    def __init__(self, add_bedrooms_per_room=True,
                 total_rooms_ix=3,
                 population_ix=5,
                 households_ix=6,
                 total_bedrooms_ix=4, columns=None):
        """
        FeatureGenerator Initialization
        add_bedrooms_per_room: bool
        total_rooms_ix: int index number of total rooms columns
        population_ix: int index number of total population columns
        households_ix: int index number of  households columns
        total_bedrooms_ix: int index number of bedrooms columns
        """
        try:
            self.columns = columns
            if self.columns is not None:
                total_rooms_ix = self.columns.index(COLUMN_TOTAL_ROOMS)
                population_ix = self.columns.index(COLUMN_POPULATION)
                households_ix = self.columns.index(COLUMN_HOUSEHOLDS)
                total_bedrooms_ix = self.columns.index(COLUMN_TOTAL_BEDROOM)

            self.add_bedrooms_per_room = add_bedrooms_per_room
            self.total_rooms_ix = total_rooms_ix
            self.population_ix = population_ix
            self.households_ix = households_ix
            self.total_bedrooms_ix = total_bedrooms_ix
        except Exception as e:
            raise HousingException(e, sys) from e

    def fit(self, X, y=None):
        return self

    def transform(self, X, y=None):
        try:
            room_per_household = X[:, self.total_rooms_ix] / \
                                 X[:, self.households_ix]
            population_per_household = X[:, self.population_ix] / \
                                       X[:, self.households_ix]
            if self.add_bedrooms_per_room:
                bedrooms_per_room = X[:, self.total_bedrooms_ix] / \
                                    X[:, self.total_rooms_ix]
                generated_feature = np.c_[
                    X, room_per_household, population_per_household, bedrooms_per_room]
            else:
                generated_feature = np.c_[
                    X, room_per_household, population_per_household]

            return generated_feature
        except Exception as e:
            raise HousingException(e, sys) from e



class DataTransformation:

    def __init__(self, data_transformation_config: DataTransformationConfig,
                 data_ingestion_artifact: DataIngestionArtifact,
                 data_validation_artifact: DataValidationArtifact
                 ):             
        try:
            self.data_transformation_config=data_transformation_config
            self.data_ingestion_artifact=data_ingestion_artifact
            self.data_validation_artifact=data_validation_artifact
        except Exception as e:
            raise HousingException(e,sys) from e
            
    
    def get_data_transformer_object(self)->ColumnTransformer:
        try:
            
            schema_file_path=self.data_validation_artifact.schema_file_path

            
            dataset_schema=read_yaml_file(file_path=schema_file_path)

            numerical_columns=dataset_schema[NUMERICAL_COLUMN_KEY]
            categorical_columns=dataset_schema[CATEGORICAL_COLUMN_KEY]

            num_pipeline=Pipeline(steps=[
                ('imputer',SimpleImputer(strategy='median')),
                ('FeautureGenrator',FeatureGenerator(add_bedrooms_per_room=True,
                columns=numerical_columns)),
                ('scaler',StandardScaler())
                ])
            
            cat_pipeline=Pipeline(steps=[
                ('imputer',SimpleImputer(strategy='most_frequent')),
                ('OneHotEncoder',OneHotEncoder()),
                ('scaler',StandardScaler(with_mean=False))
            ])

            logging.info(f"Categorical columns: {categorical_columns}")
            logging.info(f"Numerical columns: {numerical_columns}")

            preprocessing=ColumnTransformer([
                ('num_pipeline',num_pipeline,numerical_columns),
                ('cat_pipeline',cat_pipeline,categorical_columns),
            ])

            return preprocessing

        except Exception as e:
            raise HousingException(e,sys) from e
    

    def initiate_data_tranformation(self) -> DataTransformationArtifact:
        try:
            logging.info(f"Obtaining preprocessing object.")
            preprocessing_obj=self.get_data_transformer_object()

            logging.info(f"Obtaining training and test file path.")
            train_file_path=self.data_ingestion_artifact.train_file_path
            test_file_path=self.data_ingestion_artifact.test_file_path

            schema_path=self.data_validation_artifact.schema_file_path

            logging.info(f"Loading training and test data as pandas dataframe.")
            train_df=load_data(file_path=train_file_path,schema_path=schema_path)
            test_df=load_data(file_path=test_file_path,schema_path=schema_path)

            schema=read_yaml_file(schema_path)
            target_colname=schema[TARGET_COLUMN_KEY]

            logging.info(f"Splitting input and target feature from training and testing dataframe.")
            input_feauture_train=train_df.drop(columns=[target_colname],axis=1)
            target_feature_train=train_df[target_colname]

            input_feauture_test=test_df.drop(columns=[target_colname],axis=1)
            target_feature_test=test_df[target_colname]

            logging.info(f"Applying preprocessing object on training dataframe and testing dataframe")
            input_feature_train_arr=preprocessing_obj.fit_transform(input_feauture_train)
            input_feature_test_arr=preprocessing_obj.transform(input_feauture_test)

            train_arr= np.c_[input_feature_train_arr,np.array(target_feature_train)]
            test_arr= np.c_[input_feature_test_arr,np.array(target_feature_test)]

            train_dir=self.data_transformation_config.transformed_train_dir
            test_dir=self.data_transformation_config.transformed_test_dir

            file_path_train_name=os.path.basename(train_file_path).replace('.csv','.npz')
            file_path_test_name=os.path.basename(test_file_path).replace('.csv','.npz')

            file_path_train=os.path.join(train_dir,file_path_train_name)
            file_path_test=os.path.join(test_dir,file_path_test_name)

            logging.info(f"Saving transformed training and testing array.")
            save_numpy_array_data(file_path=file_path_train,array=train_arr)
            save_numpy_array_data(file_path=file_path_test,array=test_arr)

            preprocessing_object_file_path=self.data_transformation_config.preprocessed_object_file_path
            logging.info(f"Saving preprocessing object.")
            save_object(file_path=preprocessing_object_file_path,obj=preprocessing_obj)

            data_transformation_artifact=DataTransformationArtifact(
                transformed_train_file_path=file_path_train,
                transformed_test_file_path=file_path_test,
                preprocessing_object_file_path=preprocessing_object_file_path,
                is_transformed=True,
                message="Data transformation completed"
            )
            logging.info(f"Data transformationa artifact: {data_transformation_artifact}")
            return data_transformation_artifact

        except Exception as e:
            raise HousingException(e,sys) from e
    



