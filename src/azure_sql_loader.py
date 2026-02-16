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

def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        # Convert UUID objects to string
        if df[col].apply(lambda x: hasattr(x, "hex") if x is not None else False).any():
            df[col] = df[col].astype(str)

        # Convert datetime to ISO string
        if "datetime" in str(df[col].dtype).lower():
            df[col] = df[col].astype(str)

    return df


def load_vendor_tables():
    conn = get_connection()

    # =========================
    # VENDOR PROFILES (ENRICHED)
    # =========================
    profiles_query = """
    SELECT
        vp.Id AS vendor_id,
        vp.VendorId,
        vp.CompanyName AS vendor_name,
        vp.BusinessActivityDescription AS industry,
        vp.RegisteredState AS state,
        vp.RegisteredCity AS city,
        cl.Country AS country,
        vp.Status,
        vp.IsSupplier,
        vp.IsContractor,
        vp.IsConsultant,
        vp.IsMOF,
        vp.IsST,
        vp.IsBumiputera,
        vp.BusinessStreet1,
        vp.BusinessStreet2,
        vp.BusinessStreet3,
        vp.CreatedOn
    FROM VendorProfile vp
    LEFT JOIN CountryLocation cl
        ON vp.RegisteredCountryId = cl.CountryId
    WHERE vp.IsDeleted = 0
    """

    # =========================
    # ATTACHMENTS
    # =========================
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

    profiles = normalize_dataframe(pd.read_sql(profiles_query, conn))
    attachments = normalize_dataframe(pd.read_sql(attachments_query, conn))

    conn.close()

    # =========================
    # SAFE COLUMN NORMALIZATION
    # =========================
    profiles.columns = [c.lower() for c in profiles.columns]
    attachments.columns = [c.lower() for c in attachments.columns]

    # =========================
    # CERTIFICATIONS DERIVED FIELD
    # =========================
    def build_certifications(row):
        certs = []
        if row.get("ismof"):
            certs.append("MOF")
        if row.get("isst"):
            certs.append("ST")
        if row.get("isbumiputera"):
            certs.append("Bumiputera")
        return ",".join(certs)

    profiles["certifications"] = profiles.apply(build_certifications, axis=1)

    # =========================
    # LOCATION FIELD (for backward compatibility)
    # =========================
    profiles["location"] = (
        profiles["country"].fillna("") + " / " +
        profiles["state"].fillna("") + " / " +
        profiles["city"].fillna("")
    )

    # =========================
    # ENSURE REQUIRED COLUMNS EXIST
    # (prevents KeyError in AI layer)
    # =========================
    required_columns = [
        "vendor_id",
        "vendor_name",
        "industry",
        "country",
        "state",
        "city",
        "certifications"
    ]

    for col in required_columns:
        if col not in profiles.columns:
            profiles[col] = ""

    return profiles, attachments