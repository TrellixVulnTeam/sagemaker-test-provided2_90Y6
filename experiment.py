import sys
import time
from datetime import timezone

import boto3
from sagemaker import HyperparameterTuningJobAnalytics, Session
from smexperiments.experiment import Experiment
from smexperiments.search_expression import Filter, Operator, SearchExpression
from smexperiments.trial import Trial
from smexperiments.trial_component import TrialComponent

sess = boto3.Session()
sm = sess.client("sagemaker")
sagemaker_session = Session(sess)

# get the most recently created tuning job

list_tuning_jobs_response = sm.list_hyper_parameter_tuning_jobs(
    SortBy="CreationTime", SortOrder="Descending"
)
print(f'Found {len(list_tuning_jobs_response["HyperParameterTuningJobSummaries"])} tuning jobs.')
tuning_jobs = list_tuning_jobs_response["HyperParameterTuningJobSummaries"]
most_recently_created_tuning_job = tuning_jobs[0]
tuning_job_name = most_recently_created_tuning_job["HyperParameterTuningJobName"]
experiment_name = "example-experiment-with-tuning-jobs"
trial_name = tuning_job_name + "-trial"

print(
    f"Associate all training jobs created by {tuning_job_name} with trial {trial_name}"
)

# create the experiment if it doesn't exist
try:
    experiment = Experiment.load(experiment_name=experiment_name)
except Exception as ex:
    if "ResourceNotFound" in str(ex):
        experiment = Experiment.create(experiment_name=experiment_name)


# create the trial if it doesn't exist
try:
    trial = Trial.load(trial_name=trial_name)
except Exception as ex:
    if "ResourceNotFound" in str(ex):
        trial = Trial.create(experiment_name=experiment_name, trial_name=trial_name)
        
# get the trial components derived from the training jobs

creation_time = most_recently_created_tuning_job["CreationTime"]
creation_time = creation_time.astimezone(timezone.utc)
creation_time = creation_time.strftime("%Y-%m-%dT%H:%M:%SZ")

created_after_filter = Filter(
    name="CreationTime",
    operator=Operator.GREATER_THAN_OR_EQUAL,
    value=str(creation_time),
)

# the training job names contain the tuning job name (and the training job name is in the source arn)
source_arn_filter = Filter(
    name="TrialComponentName", operator=Operator.CONTAINS, value=tuning_job_name
)
source_type_filter = Filter(
    name="Source.SourceType", operator=Operator.EQUALS, value="SageMakerTrainingJob"
)

search_expression = SearchExpression(
    filters=[created_after_filter, source_arn_filter, source_type_filter]
)

# search iterates over every page of results by default
trial_component_search_results = list(
    TrialComponent.search(search_expression=search_expression, sagemaker_boto_client=sm)
)
print(f"Found {len(trial_component_search_results)} trial components.")

# associate the trial components with the trial
for tc in trial_component_search_results:
    print(
        f"Associating trial component {tc.trial_component_name} with trial {trial.trial_name}."
    )
    trial.add_trial_component(tc.trial_component_name)
    # sleep to avoid throttling
    time.sleep(0.5)