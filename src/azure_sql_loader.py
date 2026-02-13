import os
import pyodbc
import pandas as pd


def get_connection():
    conn_str = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={os.getenv('AZURE_SQL_SERVER')};"
        f"DATABASE={os.getenv('AZURE_SQL_DATABASE')};"
        f"UID={os.getenv('AZURE_SQL_USERNAME')};"
        f"PWD={os.getenv('AZURE_SQL_PASSWORD')};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )
    return pyodbc.connect(conn_str)


def load_vendor_tables():

    conn = get_connection()

    # --- Vendor Profile ---
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

    profiles = pd.read_sql(profiles_query, conn)

    # --- Vendor Attachments ---
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

    attachments = pd.read_sql(attachments_query, conn)

    conn.close()

    # --- Derive Certifications ---
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

    # --- Build Location Column ---
    profiles["location"] = (
        profiles["state"].fillna("") + " / " +
        profiles["city"].fillna("")
    )

    return profiles, attachments
