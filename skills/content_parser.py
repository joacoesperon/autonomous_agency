"""
========================================================================
Custom Skill: content_parser
========================================================================

Parses product/strategy data from Innovator agent reports and extracts
key metrics for content generation.

This skill reads .txt report files and extracts:
- Strategy name, symbol, timeframe
- Performance metrics (PF, Sharpe, DD, Win Rate)
- Backtest details
- Out-of-sample results
- Optimal parameters

Usage in OpenClaw:
    Use the skill content_parser to extract metrics from a strategy report:
    - Report path: "EA_developer/output/strategies/aprobadas/BotName/BotName_reporte.txt"

    Returns structured data for content creation.

========================================================================
"""

import os
import re
from typing import Dict, Optional, Any
from pathlib import Path


class ContentParserSkill:
    """Skill for parsing strategy reports into structured data"""

    def __init__(self):
        self.name = "content_parser"
        self.description = "Extract metrics and details from Innovator strategy reports"

    def execute(self, report_path: str) -> Dict[str, Any]:
        """
        Parse strategy report and extract key information.

        Args:
            report_path: Path to strategy report .txt file

        Returns:
            {
                "success": bool,
                "strategy_name": str,
                "symbol": str,
                "timeframe": str,
                "metrics": {
                    "profit_factor": float,
                    "sharpe_ratio": float,
                    "max_drawdown": float,
                    "win_rate": float,
                    "total_trades": int,
                    "net_profit": float,
                    "net_profit_pct": float
                },
                "backtest": {
                    "start_date": str,
                    "end_date": str,
                    "years": int
                },
                "oos_validation": {
                    "passed": bool,
                    "pf": float,
                    "sharpe": float
                },
                "parameters": Dict[str, Any],
                "talking_points": List[str],
                "message": str
            }
        """

        # Validate file exists
        if not os.path.exists(report_path):
            return {
                "success": False,
                "message": f"Report file not found: {report_path}"
            }

        # Read report content
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract strategy name from path or content
        strategy_name = self._extract_strategy_name(report_path, content)

        # Extract metrics
        metrics = self._extract_metrics(content)

        # Extract symbol and timeframe
        symbol = self._extract_symbol(content)
        timeframe = self._extract_timeframe(content)

        # Extract backtest period
        backtest = self._extract_backtest_period(content)

        # Extract OOS validation
        oos = self._extract_oos_validation(content)

        # Extract parameters
        parameters = self._extract_parameters(content)

        # Generate talking points
        talking_points = self._generate_talking_points(
            strategy_name=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            metrics=metrics,
            backtest=backtest,
            oos=oos
        )

        return {
            "success": True,
            "strategy_name": strategy_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "metrics": metrics,
            "backtest": backtest,
            "oos_validation": oos,
            "parameters": parameters,
            "talking_points": talking_points,
            "message": "Strategy data parsed successfully"
        }

    def _extract_strategy_name(self, report_path: str, content: str) -> str:
        """Extract strategy name from path or content"""
        # Try from path first
        path = Path(report_path)
        if "_reporte.txt" in path.name:
            return path.name.replace("_reporte.txt", "")

        # Try from content
        match = re.search(r"Estrategia:\s*(.+)", content)
        if match:
            return match.group(1).strip()

        return "Unknown Strategy"

    def _extract_metrics(self, content: str) -> Dict[str, float]:
        """Extract performance metrics"""
        metrics = {}

        # Profit Factor
        match = re.search(r"Profit Factor:\s*([\d.]+)", content, re.IGNORECASE)
        if match:
            metrics["profit_factor"] = float(match.group(1))

        # Sharpe Ratio
        match = re.search(r"Sharpe Ratio:\s*([\d.]+)", content, re.IGNORECASE)
        if match:
            metrics["sharpe_ratio"] = float(match.group(1))

        # Max Drawdown
        match = re.search(r"Max(?:imum)? Drawdown:\s*([\d.]+)%?", content, re.IGNORECASE)
        if match:
            metrics["max_drawdown"] = float(match.group(1))

        # Win Rate
        match = re.search(r"Win Rate:\s*([\d.]+)%?", content, re.IGNORECASE)
        if match:
            metrics["win_rate"] = float(match.group(1))

        # Total Trades
        match = re.search(r"Total.*?Trades:\s*(\d+)", content, re.IGNORECASE)
        if match:
            metrics["total_trades"] = int(match.group(1))

        # Net Profit
        match = re.search(r"Net Profit:\s*\$?([\d,]+\.?\d*)", content, re.IGNORECASE)
        if match:
            profit_str = match.group(1).replace(",", "")
            metrics["net_profit"] = float(profit_str)

        # Net Profit percentage
        match = re.search(r"Net Profit:.*?\(([\d.]+)%\)", content, re.IGNORECASE)
        if match:
            metrics["net_profit_pct"] = float(match.group(1))

        return metrics

    def _extract_symbol(self, content: str) -> str:
        """Extract trading symbol"""
        match = re.search(r"Symbol:\s*([A-Z]+)", content, re.IGNORECASE)
        if match:
            return match.group(1).upper()

        # Try common symbols
        for symbol in ["EURUSD", "GBPUSD", "XAUUSD", "USDJPY", "BTCUSD"]:
            if symbol in content.upper():
                return symbol

        return "Unknown"

    def _extract_timeframe(self, content: str) -> str:
        """Extract timeframe"""
        match = re.search(r"Timeframe:\s*([HMD]\d+)", content, re.IGNORECASE)
        if match:
            return match.group(1).upper()

        # Try common timeframes
        for tf in ["H1", "H4", "D1", "M15", "M30"]:
            if tf in content:
                return tf

        return "Unknown"

    def _extract_backtest_period(self, content: str) -> Dict[str, Any]:
        """Extract backtest period"""
        backtest = {}

        # Try to find year range
        match = re.search(r"(\d{4})\s*-\s*(\d{4})", content)
        if match:
            backtest["start_date"] = match.group(1)
            backtest["end_date"] = match.group(2)
            backtest["years"] = int(match.group(2)) - int(match.group(1))

        # Try to find explicit years mention
        match = re.search(r"(\d+)\s+years?", content, re.IGNORECASE)
        if match and "years" not in backtest:
            backtest["years"] = int(match.group(1))

        return backtest

    def _extract_oos_validation(self, content: str) -> Dict[str, Any]:
        """Extract out-of-sample validation results"""
        oos = {"passed": False}

        # Check if OOS mentioned and passed
        if re.search(r"out.?of.?sample.*pass", content, re.IGNORECASE):
            oos["passed"] = True

        # Extract OOS metrics
        match = re.search(r"OOS.*?PF[=:]?\s*([\d.]+)", content, re.IGNORECASE)
        if match:
            oos["pf"] = float(match.group(1))

        match = re.search(r"OOS.*?Sharpe[=:]?\s*([\d.]+)", content, re.IGNORECASE)
        if match:
            oos["sharpe"] = float(match.group(1))

        return oos

    def _extract_parameters(self, content: str) -> Dict[str, Any]:
        """Extract optimal parameters"""
        parameters = {}

        # Look for parameters section
        params_section = re.search(
            r"Optimal Parameters:(.*?)(?=\n\n|\Z)",
            content,
            re.IGNORECASE | re.DOTALL
        )

        if params_section:
            param_text = params_section.group(1)

            # Extract individual parameters
            param_matches = re.findall(
                r"(\w+)[=:]?\s*([\d.]+)",
                param_text
            )

            for name, value in param_matches:
                try:
                    # Try to convert to appropriate type
                    if '.' in value:
                        parameters[name] = float(value)
                    else:
                        parameters[name] = int(value)
                except ValueError:
                    parameters[name] = value

        return parameters

    def _generate_talking_points(
        self,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        metrics: Dict[str, float],
        backtest: Dict[str, Any],
        oos: Dict[str, Any]
    ) -> list:
        """Generate talking points for content"""

        points = []

        # Strategy type
        if "EMA" in strategy_name.upper() or "MA" in strategy_name.upper():
            points.append("Trend-following strategy")
        elif "RSI" in strategy_name.upper() or "CCI" in strategy_name.upper():
            points.append("Momentum-based strategy")
        elif "BREAKOUT" in strategy_name.upper():
            points.append("Breakout strategy")
        else:
            points.append("Systematic trading strategy")

        # Market and timeframe
        points.append(f"Designed for {symbol} {timeframe}")

        # Backtesting
        if "years" in backtest:
            points.append(f"{backtest['years']} years of backtesting")

        # Key metrics
        if metrics.get("profit_factor"):
            points.append(f"{metrics['profit_factor']:.2f} Profit Factor")

        if metrics.get("sharpe_ratio"):
            points.append(f"{metrics['sharpe_ratio']:.2f} Sharpe Ratio")

        # Validation
        if oos.get("passed"):
            points.append("Out-of-sample validated")

        # Who it's for
        if timeframe in ["H4", "D1"]:
            points.append("Ideal for swing traders")
        elif timeframe in ["H1", "M30"]:
            points.append("Suitable for active traders")
        elif timeframe in ["M5", "M15"]:
            points.append("For high-frequency traders")

        return points


# ========================================================================
# OpenClaw Skill Definition
# ========================================================================

def get_skill():
    """Return skill instance for OpenClaw to load"""
    return ContentParserSkill()


# ========================================================================
# CLI Testing
# ========================================================================

if __name__ == "__main__":
    import json

    skill = ContentParserSkill()

    print("🧪 Testing content_parser skill...")

    # Test with example report (if exists)
    test_path = "EA_developer/output/strategies/aprobadas/EMA50_200_RSI_Test/EMA50_200_RSI_Test_reporte.txt"

    if os.path.exists(test_path):
        result = skill.execute(test_path)
        print(f"\n✅ Result:\n{json.dumps(result, indent=2)}")
    else:
        print(f"\n⚠️  Test file not found: {test_path}")
        print("Create a test report or specify a different path.")
