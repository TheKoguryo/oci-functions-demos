import io
import json
import logging

import os
import oci


def run_pipeline(data_science_client, compartment_id, project_id, pipeline_id, object_name):
    create_pipeline_run_response = data_science_client.create_pipeline_run(
        create_pipeline_run_details=oci.data_science.models.CreatePipelineRunDetails(
            compartment_id=compartment_id,
            project_id=project_id,
            pipeline_id=pipeline_id,
            display_name="run by function",
            configuration_override_details=oci.data_science.models.PipelineDefaultConfigurationDetails(
                type="DEFAULT",
                environment_variables={
                    'OBJECT_NAME': object_name}
            )
        )
    )

    datasciencepipelinerun_id = create_pipeline_run_response.data.id

    return datasciencepipelinerun_id

def main():
    logging.basicConfig(level=logging.INFO)

    # Default config file and profile
    config = oci.config.from_file()
    # Non-Home Region
    config['region'] = 'ap-tokyo-1'

    data_science_client = oci.data_science.DataScienceClient(config)

    compartment_id = 'ocid1.compartment.oc1..aaaaaaaa54ryitndueosfezrxvxvcuosutofi2d6f53rbgwz2dpqrgeci7lq'
    project_id = 'ocid1.datascienceproject.oc1.ap-tokyo-1.amaaaaaavsea7yiaaytrg6ry2tk6vhsmdzdblxcizvrchorjtt4piikepmwa'
    pipeline_id = 'ocid1.datasciencepipeline.oc1.ap-tokyo-1.amaaaaaavsea7yiaubv34oeenjfxd7pclprkyffii2yotvakwrha55fvyj5a'
    resource_name = 'hello-odsc.txt'

    datasciencepipelinerun_id = run_pipeline(data_science_client, compartment_id, project_id, pipeline_id, resource_name)

    print(f"datasciencepipelinerun_id: {datasciencepipelinerun_id}")

if __name__ == "__main__":
    main()

