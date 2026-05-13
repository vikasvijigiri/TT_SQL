import json
import snowflake.connector

def main():
    with open("config/sf_credentials.json", "r") as f:
        creds = json.load(f)
    
    conn = snowflake.connector.connect(**creds, database="IDC")
    cs = conn.cursor()
    
    queries = [
        """SELECT COUNT(*) FROM IDC.IDC_V17.DICOM_ALL WHERE "Modality" = 'SM' AND "collection_name" IN ('TCGA-LUAD', 'TCGA-LUSC')""",
        
        """SELECT COUNT(*) FROM IDC.IDC_V17.DICOM_ALL WHERE "Modality" = 'SM' AND "collection_name" IN ('TCGA-LUAD', 'TCGA-LUSC') AND "ImageType"::TEXT ILIKE '%VOLUME%'""",
        
        """SELECT COUNT(*) FROM IDC.IDC_V17.DICOM_ALL WHERE "Modality" = 'SM' AND "collection_name" IN ('TCGA-LUAD', 'TCGA-LUSC') AND "ImageType"::TEXT ILIKE '%VOLUME%' AND ("LossyImageCompressionMethod"::TEXT IS NULL OR "LossyImageCompressionMethod"::TEXT != 'other')""",
        
        """SELECT COUNT(*) FROM IDC.IDC_V17.DICOM_ALL WHERE "Modality" = 'SM' AND "collection_name" IN ('TCGA-LUAD', 'TCGA-LUSC') AND "ImageType"::TEXT ILIKE '%VOLUME%' AND ("LossyImageCompressionMethod"::TEXT IS NULL OR "LossyImageCompressionMethod"::TEXT != 'other') AND "SpecimenDescriptionSequence"::TEXT ILIKE '%Tissue freezing medium%'""",
        
        """SELECT COUNT(*) FROM IDC.IDC_V17.DICOM_ALL WHERE "Modality" = 'SM' AND "collection_name" IN ('TCGA-LUAD', 'TCGA-LUSC') AND "ImageType"::TEXT ILIKE '%VOLUME%' AND ("LossyImageCompressionMethod"::TEXT IS NULL OR "LossyImageCompressionMethod"::TEXT != 'other') AND "SpecimenDescriptionSequence"::TEXT ILIKE '%Tissue freezing medium%' AND ("SpecimenDescriptionSequence"::TEXT ILIKE '%Normal%' OR "SpecimenDescriptionSequence"::TEXT ILIKE '%Tumor%')"""
    ]
    
    for i, q in enumerate(queries):
        cs.execute(q)
        print(f"Q{i+1}: {cs.fetchone()[0]}")
        
    cs.close()
    conn.close()

if __name__ == "__main__":
    main()
