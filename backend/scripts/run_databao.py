import os
from typing import NoReturn
from dotenv import load_dotenv
load_dotenv()
from sqlalchemy import create_engine

import databao.agent as bao


def fail(message: str) -> NoReturn:
    raise RuntimeError(message)


def from_env(key: str) -> str:
    return os.getenv(key) or fail(f"{key} is not set")


def main() -> None:
    # The Snowflake driver expects a file path for private_key_file.
    # Since the environment variable contains the key itself, we write it to a temp file.
    import tempfile
    pk_content = from_env("SNOWFLAKE_PRIVATE_KEY_FILE")
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pem') as tf:
        tf.write(pk_content)
        temp_pk_path = tf.name

    try:
        # 1. Snowflake Engine
        engine_sf = create_engine(
            "snowflake://{user}@{account_identifier}/{database}?warehouse={warehouse}&authenticator=oauth&token={token}".format(
                user=from_env("SNOWFLAKE_USER"),
                token=from_env("SNOWFLAKE_PASSWORD"),
                account_identifier=from_env("SNOWFLAKE_ACCOUNT"),
                database=from_env("SNOWFLAKE_DATABASE"),
                warehouse=from_env("SNOWFLAKE_WAREHOUSE"),
            )
        )

        # 2. GCP (BigQuery) Engine
        # Expects: GOOGLE_PROJECT, GOOGLE_DATASET, GOOGLE_APPLICATION_CREDENTIALS (json content)
        gcp_creds_content = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        gcp_creds_path = ""
        if gcp_creds_content:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as gtf:
                gtf.write(gcp_creds_content)
                gcp_creds_path = gtf.name
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = gcp_creds_path

        engine_gcp = create_engine(
            f"bigquery://{from_env('GOOGLE_PROJECT')}/{from_env('GOOGLE_DATASET')}"
        )

        domain = bao.domain()
        domain.add_db(engine_sf, name="IDC")
        domain.add_db(engine_gcp, name="IDC_GCP")

        model_name = os.getenv("LLM_MODEL", "bedrock:openai.gpt-oss-safeguard-120b")
        agent = bao.agent(
            domain=domain,
            name="my_agent",
            llm_config=bao.LLMConfig(name=model_name, temperature=0),
            executor_type="separate_executor",
        )

        result = agent.thread().ask("Could you provide a clean, structured dataset from dicom_all table that only includes SM images marked as VOLUME from the TCGA-LUAD and TCGA-LUSC collections, excluding any slides with compression type 'other,' where the specimen preparation step explicitly has 'Embedding medium' set to 'Tissue freezing medium,' and ensuring that the tissue type is only 'normal' or 'tumor' and the cancer subtype is reported accordingly?")
        df = result.df()
        print(df.head())
    finally:
        if os.path.exists(temp_pk_path):
            os.remove(temp_pk_path)
        if 'gcp_creds_path' in locals() and gcp_creds_path and os.path.exists(gcp_creds_path):
            os.remove(gcp_creds_path)


if __name__ == "__main__":
    main()
