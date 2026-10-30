"""Replanning logic - the key security feature."""
import structlog

logger = structlog.get_logger()


class Replanner:
    """
    Policy-aware replanning logic.
    
    When gateway says DENY/HOLD, agent MUST choose from safe_alternatives.
    NEVER retry the same business intent after a DENY.
    """
    
    def choose_safe_alternative(
        self,
        decision: dict,
        original_tool: str,
        context: dict,
    ) -> dict:
        """
        Choose safe alternative based on gateway decision.
        
        Returns:
            dict with "action" (flag/request_approval/skip/abort) and "reason"
        """
        reason_code = decision.get("reason_code", "")
        safe_alternatives = decision.get("safe_alternatives", [])
        inr_at_risk = decision.get("inr_at_risk", 0)
        
        logger.info(
            "replan.choosing_alternative",
            reason_code=reason_code,
            original_tool=original_tool,
            safe_alternatives=safe_alternatives,
            inr_at_risk=inr_at_risk,
        )
        
        # Bank name mismatch - HIGH RISK
        if reason_code == "DENY_BANK_NAME_MISMATCH":
            # Format in Indian numbering system (lakhs/crores)
            formatted_amount = self._format_indian_currency(inr_at_risk)
            return {
                "action": "flag",
                "reason": f"Bank account holder name mismatch detected ({formatted_amount} at risk). Flagging as suspicious and requesting human review.",
                "next_action": "request_approval",
            }
        
        # Price variance - potential fraud
        if reason_code == "DENY_PRICE_VARIANCE":
            formatted_amount = self._format_indian_currency(inr_at_risk)
            return {
                "action": "flag",
                "reason": f"Invoice price exceeds PO by more than 5% ({formatted_amount} excess). Flagging for review.",
            }
        
        # Quantity exceeds goods receipt
        if reason_code == "DENY_QTY_EXCEEDS_GR":
            return {
                "action": "flag",
                "reason": "Invoice quantity exceeds goods received. Flagging for verification.",
            }
        
        # Amount mismatch
        if reason_code == "DENY_AMOUNT_MISMATCH":
            return {
                "action": "flag",
                "reason": "Invoice amount does not match line items. Flagging for correction.",
            }
        
        # Freight uneconomic
        if reason_code == "DENY_FREIGHT_UNECONOMIC":
            formatted_amount = self._format_indian_currency(inr_at_risk)
            return {
                "action": "flag",
                "reason": f"Air freight not economically justified ({formatted_amount} extra cost). Flagging for review.",
            }
        
        # Signal contradicted (fake disruption)
        if reason_code == "DENY_SIGNAL_CONTRADICTED":
            return {
                "action": "flag",
                "reason": "Disruption claim contradicted by authoritative data. Possible fake alert. Flagging.",
            }
        
        # Duplicate payment
        if reason_code == "DENY_DUPLICATE_PAYMENT":
            return {
                "action": "skip",
                "reason": "Invoice already paid. Skipping.",
            }
        
        # HOLD decisions - need approval
        if decision.get("decision") == "HOLD":
            if reason_code == "HOLD_BANK_NAME_PARTIAL":
                formatted_amount = self._format_indian_currency(inr_at_risk)
                return {
                    "action": "request_approval",
                    "reason": f"Bank name partially matches supplier ({formatted_amount} at risk). Requesting human approval.",
                    "action_summary": f"Update bank account for supplier (partial name match, {formatted_amount} exposure)",
                }
            
            if reason_code == "HOLD_AMOUNT_NEEDS_APPROVAL":
                formatted_amount = self._format_indian_currency(inr_at_risk)
                return {
                    "action": "request_approval",
                    "reason": f"Amount {formatted_amount} exceeds approval threshold. Requesting authorization.",
                    "action_summary": f"High-value payment: {formatted_amount}",
                }
            
            if reason_code == "HOLD_BANK_COOLING_OFF":
                return {
                    "action": "request_approval",
                    "reason": "Bank account recently changed (cooling-off period). Requesting approval.",
                    "action_summary": "Payment to recently changed bank account",
                }
            
            if reason_code == "HOLD_ORACLE_UNAVAILABLE":
                return {
                    "action": "request_approval",
                    "reason": "External verification temporarily unavailable. Requesting human verification.",
                    "action_summary": f"Bank change for {original_tool} (oracle unavailable)",
                }
        
        # Lease/scope issues - abort
        if reason_code.startswith("DENY_LEASE") or reason_code.startswith("DENY_OBJECT_NOT_IN_SCOPE"):
            return {
                "action": "abort",
                "reason": f"Access denied: {reason_code}. Task cannot proceed.",
            }
        
        if reason_code == "DENY_CALL_BUDGET_EXHAUSTED":
            return {
                "action": "abort",
                "reason": "Tool call budget exhausted. Task cannot proceed.",
            }
        
        # Denial budget exhausted (lease suspended)
        if reason_code == "DENY_DENIAL_BUDGET_EXHAUSTED":
            return {
                "action": "abort",
                "reason": "Too many denials. Lease suspended. Aborting for safety.",
            }
        
        # Default: flag and request approval
        return {
            "action": "flag",
            "reason": f"Operation denied ({reason_code}). Flagging for human review.",
            "next_action": "request_approval" if "request_human_approval" in safe_alternatives else None,
        }
    
    def _format_indian_currency(self, amount: int) -> str:
        """
        Format amount in Indian numbering system (lakhs/crores).
        
        Examples:
        - 2500000 → ₹25,00,000
        - 270000 → ₹2,70,000
        """
        if amount >= 10000000:  # 1 crore or more
            crores = amount / 10000000
            return f"₹{crores:.2f} crore"
        elif amount >= 100000:  # 1 lakh or more
            lakhs = amount / 100000
            return f"₹{lakhs:.2f} lakh"
        else:
            # Format with Indian grouping: last 3 digits, then groups of 2
            s = str(amount)
            if len(s) <= 3:
                return f"₹{s}"
            
            # Split into last 3 and rest
            last_three = s[-3:]
            rest = s[:-3]
            
            # Add commas every 2 digits from right in the rest
            formatted_rest = ""
            while rest:
                if len(rest) > 2:
                    formatted_rest = "," + rest[-2:] + formatted_rest
                    rest = rest[:-2]
                else:
                    formatted_rest = rest + formatted_rest
                    break
            
            return f"₹{formatted_rest},{last_three}"
