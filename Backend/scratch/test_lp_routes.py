import sys
import os

# Add Backend folder to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.energy_resilience import build_all_blend_recipes, build_route_comparison

def test_blend_optimizer():
    print("=== Testing LP Blend Optimizer ===")
    result = build_all_blend_recipes("iranian_light")
    print(f"Refineries analysed: {result['refineries_analysed']}")
    print(f"Feasible: {result['feasible_count']}, Infeasible: {result['infeasible_count']}")
    
    for recipe in result["blend_recipes"]:
        print(f"\nRefinery: {recipe['refinery']['name']} (Status: {recipe['status']})")
        if recipe["status"] == "optimal":
            print("  Recipe:")
            for item in recipe["recipe"]:
                print(f"    - {item['crude']['name']}: {item['fraction_pct']}% ({item['daily_mbd']} mbd)")
            print(f"  Blended Properties:")
            print(f"    API Gravity: {recipe['blend_properties']['api_gravity']}")
            print(f"    Sulfur: {recipe['blend_properties']['sulfur_pct']}%")
            print(f"    Viscosity: {recipe['blend_properties']['viscosity_cst']} cSt")
            print(f"    Meets Spec: {recipe['meets_spec']}")

def test_route_comparison():
    print("\n=== Testing Suez vs Cape Route Comparison ===")
    # High risk (Red Sea/Bab el-Mandeb)
    print("\n[Crisis Risk Score = 0.85]")
    result_crisis = build_route_comparison(corridor_risk_score=0.85)
    print(f"Recommendation: {result_crisis['recommendation']} ({result_crisis['recommendation_text']})")
    print(f"Cost Delta (Cape vs Suez): ${result_crisis['cost_delta_usd']/1e3:.1f}k")
    print(f"Time Delta (Cape vs Suez): {result_crisis['time_delta_days']} days")
    print(f"Risk Reduction: {result_crisis['risk_reduction']}")
    print(f"Suez War-risk Premium: {result_crisis['war_risk_suez'] * 100}%")
    print(f"Cape War-risk Premium: {result_crisis['war_risk_cape'] * 100}%")
    
    # Low risk
    print("\n[Normal Risk Score = 0.15]")
    result_normal = build_route_comparison(corridor_risk_score=0.15)
    print(f"Recommendation: {result_normal['recommendation']} ({result_normal['recommendation_text']})")
    print(f"Cost Delta (Cape vs Suez): ${result_normal['cost_delta_usd']/1e3:.1f}k")
    print(f"Time Delta (Cape vs Suez): {result_normal['time_delta_days']} days")
    print(f"Breakeven Risk Threshold: {result_normal['breakeven_risk'] * 100}%")

if __name__ == "__main__":
    test_blend_optimizer()
    test_route_comparison()
