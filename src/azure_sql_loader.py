import os
import pymssql
import pandas as pd


def get_connection():
    return pymssql.connect(
        server=os.getenv("AZURE_SQL_SERVER"),
        user=os.getenv("AZURE_SQL_USERNAME"),
        password=os.getenv("AZURE_SQL_PASSWORD"),
        database=os.getenv("AZURE_SQL_DATABASE"),
        port=1433
    )


def load_vendor_tables():
    conn = get_connection()

    profiles_query = """
    SELECT
        Id AS vendor_id,
        VendorId,
        CompanyName AS vendor_name,
        BusinessActivityDescription AS industry,
        RegisteredState AS state,
        RegisteredCity AS city,
        Status,
        IsSupplier,
        IsContractor,
        IsConsultant,
        IsMOF,
        IsST,
        IsBumiputera,
        BusinessStreet1,
        BusinessStreet2,
        BusinessStreet3
    FROM VendorProfile
    WHERE IsDeleted = 0
    """

    attachments_query = """
    SELECT
        Id AS attachment_id,
        VendorProfileId AS vendor_id,
        FileName,
        DocumentCategory,
        DocumentType,
        FileURL
    FROM VendorAttachment
    WHERE IsDeleted = 0
    """

    profiles = pd.read_sql(profiles_query, conn)
    attachments = pd.read_sql(attachments_query, conn)

    conn.close()

    profiles["certifications"] = profiles.apply(
        lambda row: ",".join(
            [
                "MOF" if row.get("IsMOF") else "",
                "ST" if row.get("IsST") else "",
                "Bumiputera" if row.get("IsBumiputera") else ""
            ]
        ).strip(","),
        axis=1
    )

    profiles["location"] = (
        profiles["state"].fillna("") + " / " +
        profiles["city"].fillna("")
    )

    return profiles, attachments
