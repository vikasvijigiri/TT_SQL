import json
import snowflake.connector

def main():
    with open("config/sf_credentials.json", "r") as f:
        creds = json.load(f)
    
    conn = snowflake.connector.connect(**creds, database="IDC")
    cs = conn.cursor()
    
    sql = """
    SELECT "ImageType", "SpecimenDescriptionSequence"
    FROM IDC.IDC_V17.DICOM_ALL
    WHERE "Modality" = 'SM' 
      AND "collection_name" IN ('TCGA-LUAD', 'TCGA-LUSC')
    LIMIT 5
    """
    cs.execute(sql)
    for row in cs.fetchall():
        print("ImageType:", row[0])
        print("SpecimenDescriptionSequence:", row[1])
        print("-" * 50)
        
    cs.close()
    conn.close()

if __name__ == "__main__":
    main()
