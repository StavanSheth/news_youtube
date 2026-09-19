"""Theme template inheritance and layered resolution engine."""

from __future__ import annotations

import copy
from typing import Any


class ThemeTemplateRegistry:
    """Registry and inheritance resolver for theme templates."""

    TEMPLATES: dict[str, dict[str, Any]] = {
        "technology_capability": {
            "questions": ["what_capability_changed", "what_evidence_validates_it", "what_are_practical_limits"],
            "evidence_requirements": ["primary_source", "reproducible_benchmark", "implementation_details"],
            "significance_rules": {
                "significant_if": ["new_state_of_art_reached", "new_architecture_open_sourced", "efficiency_gain_over_2x"],
                "insignificant_if": ["unsubstantiated_marketing_claim", "minor_version_bump_without_metrics"],
            },
            "stream_rules": {
                "news": {"freshness": "48h", "focus": ["new_capabilities", "benchmarks", "industry_adoption"]},
                "video": {"focus": ["demos", "code_walkthroughs", "benchmarks", "technical_limitations"]},
            },
            "no_update_policy": {
                "NO_MAJOR_UPDATE": "No verified technological capability change was identified in this period.",
                "INSUFFICIENT_EVIDENCE": "Available evidence does not corroborate claimed capability improvements.",
            },
            "output_requirements": {
                "report_type": "technical_deep_dive",
                "sections": ["summary", "capability", "evidence", "limitations", "implications", "sources"],
            },
        },
        "technology_infrastructure": {
            "questions": ["what_infrastructure_changed", "what_capacity_is_affected", "what_is_supply_chain_impact"],
            "evidence_requirements": ["fab_operational_data", "vendor_announcement", "procurement_filing"],
            "significance_rules": {
                "significant_if": ["fab_groundbreaking_or_first_silicon", "export_restriction_implemented", "process_node_milestone"],
                "insignificant_if": ["routine_maintenance", "speculative_rumors_without_sourcing"],
            },
            "stream_rules": {
                "news": {"freshness": "72h", "focus": ["capacity", "yields", "equipment", "export_controls"]},
                "video": {"focus": ["facility_tours", "technical_analysis", "supply_chain_deep_dives"]},
            },
            "no_update_policy": {
                "NO_MAJOR_UPDATE": "No material semiconductor or infrastructure capacity change was verified.",
                "INSUFFICIENT_EVIDENCE": "Reported infrastructure updates lacked verifiable confirmation.",
            },
            "output_requirements": {
                "report_type": "technical_deep_dive",
                "sections": ["summary", "evidence", "capacity", "dependencies", "implications", "sources"],
            },
        },
        "security_incident": {
            "questions": ["what_vulnerability_or_breach_occurred", "what_systems_are_affected", "is_there_active_exploitation", "what_mitigation_exists"],
            "evidence_requirements": ["cve_advisory", "security_vendor_report", "confirmed_poc", "cisa_kev_entry"],
            "significance_rules": {
                "significant_if": ["in_the_wild_zero_day_exploitation", "critical_infrastructure_breached", "cvss_score_above_9"],
                "insignificant_if": ["informational_finding_without_exploit", "theoretical_unverified_attack"],
            },
            "stream_rules": {
                "news": {"freshness": "24h", "focus": ["affected_versions", "indicators_of_compromise", "patches"]},
                "video": {"focus": ["poc_demonstration", "threat_actor_analysis", "defense_hardening"]},
            },
            "no_update_policy": {
                "NO_MAJOR_UPDATE": "No critical vulnerabilities or active exploits were confirmed in this window.",
                "INSUFFICIENT_EVIDENCE": "Reported incidents could not be independently corroborated with CVE or telemetry.",
            },
            "output_requirements": {
                "report_type": "executive_brief",
                "sections": ["summary", "threat_vector", "affected_systems", "mitigation", "sources"],
            },
        },
        "space_mission": {
            "questions": ["what_mission_milestone_occurred", "what_launch_vehicle_was_involved", "what_technical_objectives_were_met"],
            "evidence_requirements": ["telemetry_data", "launch_manifest", "space_agency_confirmation"],
            "significance_rules": {
                "significant_if": ["orbital_insertion_success_or_failure", "new_launch_vehicle_debut", "lunar_or_deep_space_milestone"],
                "insignificant_if": ["routine_static_fire_test", "speculative_future_launch_dates"],
            },
            "stream_rules": {
                "news": {"freshness": "48h", "focus": ["launch_results", "anomaly_reports", "program_budgets"]},
                "video": {"focus": ["launch_broadcasts", "technical_breakdowns", "hardware_inspections"]},
            },
            "no_update_policy": {
                "NO_MAJOR_UPDATE": "No orbital launch or mission milestone was recorded during this timeframe.",
                "INSUFFICIENT_EVIDENCE": "Space operations reports lack official launch authority or tracking data.",
            },
            "output_requirements": {
                "report_type": "technical_deep_dive",
                "sections": ["summary", "mission_profile", "technical_milestone", "risks", "sources"],
            },
        },
        "market_update": {
            "questions": ["what_macro_indicator_changed", "what_was_the_policy_action", "what_is_market_transmission"],
            "evidence_requirements": ["central_bank_statement", "statistical_agency_release", "yield_curve_data"],
            "significance_rules": {
                "significant_if": ["rate_decision_divergence", "inflation_surprise_exceeding_consensus", "systemic_liquidity_action"],
                "insignificant_if": ["intra-day_noise_without_fundamental_catalyst", "unattributed_commentary"],
            },
            "stream_rules": {
                "news": {"freshness": "24h", "focus": ["numbers", "official_rates", "policy_guidance"]},
                "video": {"focus": ["analyst_macro_models", "policy_press_conferences", "sector_rotations"]},
            },
            "no_update_policy": {
                "NO_MAJOR_UPDATE": "No unexpected macroeconomic data or central bank actions were registered.",
                "INSUFFICIENT_EVIDENCE": "Economic claims could not be verified against primary statistical releases.",
            },
            "output_requirements": {
                "report_type": "top_event",
                "sections": ["summary", "indicators", "policy_impact", "watchlist", "sources"],
            },
        },
        "geopolitical_event": {
            "questions": ["what_diplomatic_or_security_event_occurred", "who_are_the_state_actors", "what_sanctions_or_treaties_are_involved"],
            "evidence_requirements": ["government_decree", "treaty_text", "official_diplomatic_communique"],
            "significance_rules": {
                "significant_if": ["new_sanctions_regime_imposed", "territorial_or_military_escalation", "bilateral_pact_signed"],
                "insignificant_if": ["diplomatic_rhetoric_without_action", "unverified_social_media_rumor"],
            },
            "stream_rules": {
                "news": {"freshness": "24h", "focus": ["official_actions", "sanctions_lists", "security_measures"]},
                "video": {"focus": ["treaty_signings", "geopolitical_analysis", "parliamentary_debates"]},
            },
            "no_update_policy": {
                "NO_MAJOR_UPDATE": "No material geopolitical escalation or bilateral policy change occurred.",
                "INSUFFICIENT_EVIDENCE": "Claims of diplomatic shifts lacked official government confirmation.",
            },
            "output_requirements": {
                "report_type": "executive_brief",
                "sections": ["summary", "state_actions", "strategic_impact", "scenarios", "sources"],
            },
        },
        "policy_regulation": {
            "questions": ["what_regulatory_action_was_taken", "which_authority_issued_it", "what_is_compliance_timeline"],
            "evidence_requirements": ["gazette_publication", "regulator_notice", "enacted_statute"],
            "significance_rules": {
                "significant_if": ["enacted_legislation", "formal_antitrust_enforcement_action", "mandatory_licensing_regime"],
                "insignificant_if": ["preliminary_hearing_discussion", "non-binding_advisory_opinion"],
            },
            "stream_rules": {
                "news": {"freshness": "48h", "focus": ["statutory_deadlines", "enforcement_penalties", "covered_entities"]},
                "video": {"focus": ["regulatory_testimony", "legal_expert_roundtables", "compliance_briefings"]},
            },
            "no_update_policy": {
                "NO_MAJOR_UPDATE": "No major regulatory or legislative actions were enacted in this review period.",
                "INSUFFICIENT_EVIDENCE": "Regulatory rumors were not supported by official docket or gazette filings.",
            },
            "output_requirements": {
                "report_type": "executive_brief",
                "sections": ["summary", "regulatory_change", "compliance_impact", "timeline", "sources"],
            },
        },
        "startup_financing": {
            "questions": ["what_financing_round_closed", "what_was_the_valuation_and_lead_investor", "what_is_the_technology_thesis"],
            "evidence_requirements": ["sec_form_d", "press_release_from_lead_investor", "confirmed_term_sheet"],
            "significance_rules": {
                "significant_if": ["series_b_or_above_exceeding_50m", "tier_1_firm_lead_investment", "first_institutional_round_in_new_domain"],
                "insignificant_if": ["unspecified_angel_round", "undisclosed_funding_without_investors"],
            },
            "stream_rules": {
                "news": {"freshness": "48h", "focus": ["deal_size", "lead_investors", "strategic_backers"]},
                "video": {"focus": ["founder_pitches", "vc_investment_theses", "product_demos"]},
            },
            "no_update_policy": {
                "NO_MAJOR_UPDATE": "No significant venture funding rounds or venture transactions closed.",
                "INSUFFICIENT_EVIDENCE": "Financing reports lacked primary investor confirmation or regulatory filings.",
            },
            "output_requirements": {
                "report_type": "executive_brief",
                "sections": ["summary", "transaction_details", "investor_syndicate", "market_context", "sources"],
            },
        },
        "research_breakthrough": {
            "questions": ["what_scientific_finding_was_demonstrated", "what_methodology_or_evidence_supports_it", "what_are_the_limits"],
            "evidence_requirements": ["peer_reviewed_paper", "arxiv_preprint_with_code", "reproducible_experimental_data"],
            "significance_rules": {
                "significant_if": ["peer_reviewed_in_tier_1_journal", "independent_experimental_replication", "quantum_or_physical_threshold_crossed"],
                "insignificant_if": ["unreviewed_speculative_claim", "paper_lacking_baseline_comparisons"],
            },
            "stream_rules": {
                "news": {"freshness": "72h", "focus": ["peer_review_status", "methodology", "data_tables"]},
                "video": {"focus": ["author_paper_presentations", "code_walkthroughs", "lab_benchmarks"]},
            },
            "no_update_policy": {
                "NO_MAJOR_UPDATE": "No breakthrough research papers or verified experimental findings were identified.",
                "INSUFFICIENT_EVIDENCE": "Reported scientific claims were not corroborated by preprints, code, or peer review.",
            },
            "output_requirements": {
                "report_type": "technical_deep_dive",
                "sections": ["summary", "scientific_finding", "methodology", "limitations", "implications", "sources"],
            },
        },
    }

    def __init__(self, custom_templates: dict[str, Any] | None = None) -> None:
        self._templates = dict(self.TEMPLATES)
        if custom_templates:
            self._templates.update(custom_templates)

    def resolve(self, template_id: str, overrides: dict[str, Any]) -> dict[str, Any]:
        """Resolve a theme dict by layering overrides over the base template."""
        base = copy.deepcopy(self._templates.get(template_id, self.TEMPLATES.get("technology_capability", {})))
        merged = copy.deepcopy(base)

        for key, value in overrides.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key].update(value)
            elif isinstance(value, list) and isinstance(merged.get(key), list):
                # Prepend or override list items
                merged[key] = value
            else:
                merged[key] = value

        return merged

    def inspect_origin(self, theme: dict[str, Any], template_id: str | None = None) -> dict[str, list[str]]:
        """Identify which fields originate from exact overrides versus the template base."""
        t_id = template_id or theme.get("template") or "technology_capability"
        base = self._templates.get(t_id, {})

        exact_fields = []
        template_fields = []

        for key in theme:
            if key in {"id", "theme_id", "micro_topic_id", "micro_topic", "domain", "topic"}:
                exact_fields.append(key)
            elif key in base:
                if theme[key] != base[key]:
                    exact_fields.append(key)
                else:
                    template_fields.append(key)
            else:
                exact_fields.append(key)

        return {
            "exact_fields": sorted(exact_fields),
            "template_fields": sorted(template_fields),
        }
