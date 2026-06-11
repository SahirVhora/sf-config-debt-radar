import textwrap

from sf_config_debt_radar.auth import build_basic_auth_header, derive_token_url
from sf_config_debt_radar.metadata import parse_metadata_xml, classify_ec_entities
from sf_config_debt_radar.scoring import score_debt
from sf_config_debt_radar.report import build_report_model


SAMPLE_METADATA = textwrap.dedent("""
<edmx:Edmx xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx" xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata">
  <edmx:DataServices>
    <Schema xmlns="http://schemas.microsoft.com/ado/2008/09/edm" Namespace="SFOData">
      <EntityType Name="EmpJob">
        <Property Name="userId" Type="Edm.String" Nullable="false" />
        <Property Name="eventReason" Type="Edm.String" Nullable="true" />
        <Property Name="customString12" Type="Edm.String" Nullable="true" MaxLength="256" sap:label="Retention risk" xmlns:sap="http://www.sap.com/Protocols/SAPData" />
        <Property Name="customString13" Type="Edm.String" Nullable="true" MaxLength="256" />
        <Property Name="startDate" Type="Edm.DateTime" Nullable="false" />
        <Property Name="lastModifiedDateTime" Type="Edm.DateTime" Nullable="true" />
      </EntityType>
      <EntityType Name="Position">
        <Property Name="code" Type="Edm.String" Nullable="false" />
        <Property Name="effectiveStartDate" Type="Edm.DateTime" Nullable="false" />
        <Property Name="effectiveStatus" Type="Edm.String" Nullable="true" />
        <NavigationProperty Name="departmentNav" ToRole="Department" />
      </EntityType>
      <EntityType Name="cust_ProjectThing">
        <Property Name="externalCode" Type="Edm.String" Nullable="false" />
        <Property Name="cust_owner" Type="Edm.String" Nullable="true" />
      </EntityType>
    </Schema>
  </edmx:DataServices>
</edmx:Edmx>
""")


def test_basic_auth_header_uses_username_at_company_format():
    header = build_basic_auth_header("admin@ACME", "secret")
    assert header.startswith("Basic ")
    assert header == "Basic YWRtaW5AQUNNRTpzZWNyZXQ="


def test_token_url_is_derived_from_odata_host():
    assert (
        derive_token_url("https://api55.sapsf.eu/odata/v2/")
        == "https://api55.sapsf.eu/oauth/token"
    )


def test_metadata_parser_extracts_entities_fields_and_effective_dates():
    entities = parse_metadata_xml(SAMPLE_METADATA)
    assert entities["EmpJob"]["field_count"] == 6
    assert entities["EmpJob"]["custom_field_count"] == 1
    assert entities["Position"]["has_effective_start_date"] is True
    assert entities["Position"]["nav_props"][0]["name"] == "departmentNav"


def test_classify_ec_entities_finds_core_and_custom_entities():
    entities = parse_metadata_xml(SAMPLE_METADATA)
    classified = classify_ec_entities(entities)
    assert "EmpJob" in classified["core_ec"]
    assert "Position" in classified["core_ec"]
    assert "cust_ProjectThing" in classified["custom_mdf"]


def test_metadata_parser_ignores_inactive_delivered_custom_slots():
    entities = parse_metadata_xml(SAMPLE_METADATA)
    fields = {field["name"]: field for field in entities["EmpJob"]["fields"]}
    assert fields["customString12"]["is_custom"] is True
    assert fields["customString13"]["is_custom"] is False
    assert entities["EmpJob"]["custom_field_count"] == 1


def test_scoring_prioritises_high_risk_business_rules_rbp_and_fields():
    findings = [
        {"severity": "HIGH", "area": "Business Rules"},
        {"severity": "HIGH", "area": "RBP"},
        {"severity": "MEDIUM", "area": "Custom Fields"},
        {"severity": "LOW", "area": "Picklists"},
    ]
    scored = score_debt(findings)
    assert scored["overall_score"] < 85
    assert scored["area_scores"]["Business Rules"] < scored["area_scores"]["Picklists"]
    assert scored["risk_level"] in {"Medium", "High", "Critical"}


def test_report_model_contains_summary_findings_and_roadmap():
    metadata_summary = {"entity_count": 3, "custom_mdf_count": 1, "ec_entity_count": 2}
    findings = [
        {
            "severity": "HIGH",
            "area": "Custom Fields",
            "title": "Hidden field debt",
            "detail": "customString12 appears unused",
        }
    ]
    report = build_report_model(metadata_summary, findings)
    assert report["summary"]["entity_count"] == 3
    assert report["score"]["overall_score"] <= 100
    assert len(report["roadmap"]) == 3
    assert report["findings"][0]["title"] == "Hidden field debt"
