"""
Report generation module.

This module contains all HTML report generation functionality:
- HTML report generation with modern styling
- Solution summary creation
- Weighted absorption calculations for minerals
- Table formatting for animal info, requirements, diet composition
- Feed selection display utilities
"""

import numpy as np
import pandas as pd
import os
from pathlib import Path

# Import from animal_requirements for table creation
from .animal_requirements import rsm_create_animal_requirements_dataframe

# Import from utilities
from .utilities import rename_variable, replace_na_and_negatives

def calculate_weighted_absorption(dt_forages, dt_concentrates):
    #Get proportions from the Total rows in forage and concentrate tables
    # Extract from the "Total" rows in each dataframe
    forage_total_row = dt_forages[dt_forages['Name'] == 'Total']
    concentrate_total_row = dt_concentrates[dt_concentrates['Name'] == 'Total']
    
    if not forage_total_row.empty and not concentrate_total_row.empty:
        # Get the DMI percentages from the Total rows
        forage_prop = forage_total_row.iloc[0]['DM_prop'] / 100.0      # 45.12% → 0.4512
        concentrate_prop = concentrate_total_row.iloc[0]['DM_prop'] / 100.0  # 54.87% → 0.5487
        mineral_prop = 1.0 - forage_prop - concentrate_prop        # 0.25% → 0.0025
        
        # Calculate weighted absorption coefficients
        weighted_ca = (forage_prop * 0.40 + concentrate_prop * 0.60 + mineral_prop * 0.60)
        weighted_p = (forage_prop * 0.64 + concentrate_prop * 0.70 + mineral_prop * 0.70)
        
        return weighted_ca, weighted_p
    
    return 0.50, 0.67  # Fallback defaults

def rsm_generate_report(post_results, animal_requirements, output_file="final_report.html", user_name="User", simulation_id="N/A", report_id="N/A"):
    """
    Generate HTML report from post-optimization analysis results.
    
    Parameters:
    -----------
    post_results : dict
        Dictionary returned from run_post_optimization_analysis()
    animal_requirements : dict
        Animal requirements dictionary from calculate_an_requirements()
    output_file : str
        Output HTML file path
    user_name : str
        User name for the report header
    simulation_id : str
        Simulation ID for the report header
    report_id : str
        Report ID for the report header
    """
    
    # Check if analysis was successful
    if post_results['status'] != 'SUCCESS':
        print(f"❌ Cannot generate report: Analysis status is {post_results['status']}")
        return
    
    # Extract data from post_results dictionary
    animal_inputs = post_results['animal_inputs']
    dt_proportions = post_results['dt_proportions']
    dt_forages = post_results['dt_forages']
    methane_report = post_results['methane_report']
    ration_evaluation = post_results['ration_evaluation']
    
    # Create Dt_results from dt_proportions
    dt_results = dt_proportions[['Name', 'AF_kg', 'PRICE/KG', 'Cost']].copy()
    
    # Create An_Requirements DataFrame from animal_requirements dictionary
    An_Requirements = rsm_create_animal_requirements_dataframe(animal_requirements, post_results['intermediate_results_values'])

    # Update water intake with calculated value
    An_Requirements.loc[An_Requirements['Parameter'] == 'Water Intake', 'Value'] = post_results['water_intake']

    # Get concentrates from dt_proportions
    dt_concentrates = dt_proportions[
        (dt_proportions['Ingr_Type'] == 'Concentrate') | 
        (dt_proportions['Ingr_Type'] == 'Minerals') |
        (dt_proportions['Ingr_Type'] == 'By-Product/Other') |
        (dt_proportions['Ingr_Type'] == 'Plant Protein') |
        (dt_proportions['Ingr_Type'] == 'Additive')
    ].copy()
    
    # Add concentrate totals if not empty
    if not dt_concentrates.empty:
        concentrate_total = dt_concentrates.select_dtypes(include=[np.number]).sum()
        concentrate_total['Ingr_Type'] = 'Concentrate'
        concentrate_total['Name'] = 'Total'
        dt_concentrates = pd.concat([dt_concentrates, concentrate_total.to_frame().T], ignore_index=True)
    
    # Calculate weighted absorption coefficients for Ca and P display conversion
    weighted_ca, weighted_p = calculate_weighted_absorption(dt_forages, dt_concentrates)

    # Get current absorbed values
    ca_absorbed = animal_requirements.get("An_Ca_req", 0)
    p_absorbed = animal_requirements.get("An_P_req", 0)

    # Convert to crude using weighted coefficients for display
    ca_crude = (ca_absorbed / weighted_ca)*1000
    p_crude = (p_absorbed / weighted_p)*1000 

    # Update display values in requirements table
    An_Requirements.loc[An_Requirements['Parameter'] == 'Calcium', 'Value'] = ca_crude
    An_Requirements.loc[An_Requirements['Parameter'] == 'Phosphorus', 'Value'] = p_crude

    # Update water intake with calculated value (water fix)
    An_Requirements.loc[An_Requirements['Parameter'] == 'Water Intake', 'Value'] = post_results['water_intake']

    # Round all numeric columns
    dfs = [animal_inputs, An_Requirements, dt_results, dt_proportions, dt_forages, dt_concentrates, methane_report, ration_evaluation]
    for df in dfs:
        if not df.empty:
            num_cols = df.select_dtypes(include=[np.number]).columns
            df[num_cols] = df[num_cols].round(2)

    # Add solution summary information
    solution_summary = rsm_create_solution_summary(post_results, animal_requirements)

    # Custom CSS for modern, beautiful design
    style = """
    <style>
      * { box-sizing: border-box; }
      
      body { 
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
        margin: 0; 
        padding: 20px; 
        line-height: 1.6; 
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        min-height: 100vh;
      }
      
      .container {
        max-width: 1200px;
        margin: 0 auto;
        background: white;
        border-radius: 15px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        overflow: hidden;
      }
      
      .header {
        background: linear-gradient(135deg, #2e7d32 0%, #388e3c 100%);
        color: white;
        padding: 30px;
        text-align: center;
      }
      
      .header h1 {
        margin: 0;
        font-size: 2.5em;
        font-weight: 300;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
      }
      
      .report-meta {
        display: flex;
        justify-content: space-between;
        gap: 5px;
        margin-top: 11.25px;
        padding: 7.5px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        flex-wrap: wrap;
      }
      
      .meta-item {
        color: white;
        font-size: 0.8em;
        padding: 2px 4px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 6px;
        flex: 1 1 auto;
        min-width: 100px;
        text-align: center;
        display: flex;
        flex-direction: column;
        gap: 2px;
      }
      
      .meta-item strong {
        color: #e8f5e8;
        margin-bottom: 1px;
        font-size: 0.9em;
      }
      
      .meta-item .meta-value {
        color: white;
        font-weight: 500;
        font-size: 0.85em;
      }
      
      .content {
        padding: 30px;
      }
      
      h2 { 
        color: #2e7d32; 
        margin-top: 40px; 
        margin-bottom: 20px; 
        font-size: 1.8em; 
        font-weight: 500;
        border-bottom: 3px solid #4caf50;
        padding-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 10px;
      }
      
      h3 { 
        color: #388e3c; 
        margin-top: 25px; 
        margin-bottom: 15px; 
        font-size: 1.3em; 
        font-weight: 500;
      }
      
      .table-container {
        background: white;
        border-radius: 10px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        margin: 20px 0;
        overflow: hidden;
        max-width: 100%;
        overflow-x: auto;
      }
      
      table { 
        border-collapse: collapse; 
        width: auto;
        min-width: 100%;
        margin: 0;
        font-size: 14px;
        background: white;
        table-layout: auto;
      }
      
      th, td { 
        padding: 10px 12px; 
        text-align: left; 
        border-bottom: 1px solid #e0e0e0;
        white-space: nowrap;
        max-width: 200px;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      
      /* Specific column width adjustments for different table types (reduced by another 30%) */
      .animal-info-table th:nth-child(1),
      .animal-info-table td:nth-child(1) { width: 81px; }
      .animal-info-table th:nth-child(2),
      .animal-info-table td:nth-child(2) { width: 54px; }
      .animal-info-table th:nth-child(3),
      .animal-info-table td:nth-child(3) { width: 36px; }
      
      .requirements-table th:nth-child(1),
      .requirements-table td:nth-child(1) { width: 90px; }
      .requirements-table th:nth-child(2),
      .requirements-table td:nth-child(2) { width: 45px; }
      .requirements-table th:nth-child(3),
      .requirements-table td:nth-child(3) { width: 36px; }
      
      .diet-table th:nth-child(1),
      .diet-table td:nth-child(1) { width: 35%; }
      .diet-table th:nth-child(2),
      .diet-table td:nth-child(2) { width: 20%; }
      .diet-table th:nth-child(3),
      .diet-table td:nth-child(3) { width: 20%; }
      .diet-table th:nth-child(4),
      .diet-table td:nth-child(4) { width: 25%; }
      
      .proportions-table th:nth-child(1),
      .proportions-table td:nth-child(1) { width: 81px; }
      .proportions-table th:nth-child(2),
      .proportions-table td:nth-child(2) { width: 54px; }
      .proportions-table th:nth-child(3),
      .proportions-table td:nth-child(3) { width: 36px; }
      .proportions-table th:nth-child(4),
      .proportions-table td:nth-child(4) { width: 36px; }
      .proportions-table th:nth-child(5),
      .proportions-table td:nth-child(5) { width: 36px; }
      
      .forage-table th:nth-child(1),
      .forage-table td:nth-child(1) { width: 67px; }
      .forage-table th:nth-child(2),
      .forage-table td:nth-child(2) { width: 45px; }
      .forage-table th:nth-child(3),
      .forage-table td:nth-child(3) { width: 36px; }
      
      .concentrate-table th:nth-child(1),
      .concentrate-table td:nth-child(1) { width: 67px; }
      .concentrate-table th:nth-child(2),
      .concentrate-table td:nth-child(2) { width: 45px; }
      .concentrate-table th:nth-child(3),
      .concentrate-table td:nth-child(3) { width: 36px; }
      
      .environmental-table th:nth-child(1),
      .environmental-table td:nth-child(1) { width: 81px; }
      .environmental-table th:nth-child(2),
      .environmental-table td:nth-child(2) { width: 54px; }
      .environmental-table th:nth-child(3),
      .environmental-table td:nth-child(3) { width: 45px; }
      
      th { 
        background: linear-gradient(135deg, #4caf50 0%, #66bb6a 100%);
        color: white;
        font-weight: 600;
        font-size: 14px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      
      tr:hover { 
        background-color: #f8f9fa; 
        transition: background-color 0.3s ease;
      }
      
      tr:nth-child(even) { 
        background-color: #fafafa; 
      }
      
      .summary-box { 
        background: linear-gradient(135deg, #e8f5e8 0%, #c8e6c9 100%);
        border: none;
        border-radius: 15px; 
        padding: 25px; 
        margin: 25px 0; 
        box-shadow: 0 4px 15px rgba(76, 175, 80, 0.2);
      }
      
      .status-optimal { 
        color: #2e7d32; 
        font-weight: 600;
        background: #e8f5e8;
        padding: 5px 12px;
        border-radius: 20px;
        display: inline-block;
      }
      
      .status-marginal { 
        color: #f57c00; 
        font-weight: 600;
        background: #fff3e0;
        padding: 5px 12px;
        border-radius: 20px;
        display: inline-block;
      }
      
      .status-infeasible { 
        color: #d32f2f; 
        font-weight: 600;
        background: #ffebee;
        padding: 5px 12px;
        border-radius: 20px;
        display: inline-block;
      }
      
      .cost-highlight { 
        background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%);
        font-weight: 600;
        padding: 8px 15px;
        border-radius: 8px;
        border-left: 4px solid #ff9800;
      }
      
      .metric-card {
        background: white;
        border-radius: 10px;
        padding: 20px;
        margin: 15px 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        border-left: 4px solid #4caf50;
      }
      
      .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 20px;
        margin: 20px 0;
      }
      
      .metric-item {
        background: white;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        text-align: center;
        border-top: 4px solid #4caf50;
      }
      
      .metric-value {
        font-size: 2em;
        font-weight: 600;
        color: #2e7d32;
        margin: 10px 0;
      }
      
      .metric-label {
        color: #666;
        font-size: 0.9em;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      
      .section {
        margin: 30px 0;
        padding: 25px;
        background: white;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
      }
      
      .emoji {
        font-size: 1.2em;
      }
      
      @media (max-width: 768px) {
        .container {
          margin: 10px;
          border-radius: 10px;
        }
        
        .content {
          padding: 20px;
        }
        
        .header h1 {
          font-size: 2em;
        }
        
        .metric-grid {
          grid-template-columns: 1fr;
        }
        
        table {
          font-size: 12px;
        }
        
        th, td {
          padding: 8px 10px;
        }
      }
    </style>
    """

    # Get current date and time for report generation
    from datetime import datetime
    report_date = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    # Assemble HTML with modern structure
    html_parts = [
        "<!DOCTYPE html>",
        "<html><head>",
        "<meta charset='utf-8'/>",
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>",
        "<title>Ration Formulation Report</title>",
        style,
        "</head><body>",
        
        "<div class='container'>",
        "<div class='header'>",
        "<h1>🐄 Ration Formulation Report</h1>",
        "<div class='report-meta'>",
        f"<div class='meta-item'><strong>User</strong><span class='meta-value'>{user_name}</span></div>",
        f"<div class='meta-item'><strong>Simulation ID</strong><span class='meta-value'>{simulation_id}</span></div>",
        f"<div class='meta-item'><strong>Report ID</strong><span class='meta-value'>{report_id}</span></div>",
        f"<div class='meta-item'><strong>Country</strong><span class='meta-value'>Vietnam</span></div>",
        f"<div class='meta-item'><strong>Generated</strong><span class='meta-value'>{report_date}</span></div>",
        "</div>",
        "</div>",
        
        "<div class='content'>",
        
        # Solution Summary Section
        "<div class='section'>",
        "<h2><span class='emoji'>📊</span>Solution Summary</h2>",
        "<div class='metric-grid'>",
        f"<div class='metric-item'>",
        f"<div class='metric-value'>${post_results['total_cost']:.2f}</div>",
        f"<div class='metric-label'>Daily Feed Cost</div>",
        f"</div>",
        f"<div class='metric-item'>",
        f"<div class='metric-value'>{animal_requirements.get('Trg_MilkProd_L', 0):.1f}L</div>",
        f"<div class='metric-label'>Target Milk Production</div>",
        f"</div>",
        f"<div class='metric-item'>",
        f"<div class='metric-value'>{animal_requirements.get('Trg_Dt_DMIn', 0):.2f}kg</div>",
        f"<div class='metric-label'>Dry Matter Intake</div>",
        f"</div>",
        "</div>",
        "</div>",
        
        # Animal Information
        "<div class='section'>",
        "<h2><span class='emoji'>🐄</span>Animal Information</h2>",
        "<div class='table-container'>",
        animal_inputs.to_html(index=False, escape=False, classes='animal-info-table'),
        "</div>",
        "</div>",
        
        # Animal Requirements
        "<div class='section'>",
        "<h2><span class='emoji'>📋</span>Nutritional Requirements</h2>",
        "<div class='table-container'>",
        An_Requirements.to_html(index=False, escape=False, classes='requirements-table'),
        "</div>",
        "</div>",
        
        # Diet Results
        "<div class='section'>",
        "<h2><span class='emoji'>🍽️</span>Least Cost Diet</h2>",
        "<div class='table-container'>",
        dt_results.to_html(index=False, escape=False, classes='diet-table'),
        "</div>",
        "</div>",
        
        # Detailed Proportions
        "<div class='section'>",
        "<h2><span class='emoji'>📊</span>Nutrient Proportions (%)</h2>",
        "<div class='table-container'>",
        dt_proportions.to_html(index=False, escape=False, classes='proportions-table'),
        "</div>",
        "</div>",
        
        # Forages
        "<div class='section'>",
        "<h2><span class='emoji'>🌾</span>Forage</h2>",
        "<div class='table-container'>",
        dt_forages.to_html(index=False, escape=False, classes='forage-table') if not dt_forages.empty else "<p style='text-align: center; color: #666; font-style: italic;'>No forages in this diet.</p>",
        "</div>",
        "</div>",
        
        # Concentrates
        "<div class='section'>",
        "<h2><span class='emoji'>🌽</span>Concentrate</h2>",
        "<div class='table-container'>",
        dt_concentrates.to_html(index=False, escape=False, classes='concentrate-table') if not dt_concentrates.empty else "<p style='text-align: center; color: #666; font-style: italic;'>No concentrates in this diet.</p>",
        "</div>",
        "</div>",
        
        # Methane Report
        "<div class='section'>",
        "<h2><span class='emoji'>🌍</span>Environmental Impact</h2>",
        "<div class='table-container'>",
        methane_report.to_html(index=False, escape=False, classes='environmental-table'),
        "</div>",
        "</div>",
        
        "</div>",  # Close content
        "</div>",  # Close container
        
        "</body></html>"
    ]

    html_content = "\n".join(html_parts)
    # Ensure file gets overwritten
    try:
        # Remove existing file if it exists
        if os.path.exists(output_file):
            os.remove(output_file)
            #print(f"🗑️ Removed existing file: {output_file}")
    
        # Write new file
        Path(output_file).write_text(html_content, encoding="utf-8")
        #print(f"✅ Report generated: {output_file}")
    
    except Exception as e:
        print(f"Error writing report: {e}")
        print(f"   Attempted to write to: {os.path.abspath(output_file)}")


def rsm_create_solution_summary(post_results, animal_requirements):
    """
    Create HTML summary of the solution
    """
    cost = post_results['total_cost']
    milk_production = animal_requirements.get('Trg_MilkProd_L', 0)
    dry_matter_intake = animal_requirements.get('Trg_Dt_DMIn', 0)
    
    summary_html = f"""
    <table style="width: 100%;">
        <tr class="cost-highlight">
            <td><strong>Daily Feed Cost:</strong></td>
            <td>${cost:.2f}</td>
        </tr>
        <tr>
            <td><strong>Target Milk Production:</strong></td>
            <td>{milk_production:.1f} L/day</td>
        </tr>
        <tr>
            <td><strong>Dry Matter Intake:</strong></td>
            <td>{dry_matter_intake:.2f} kg/day</td>
        </tr>
    </table>
    """
    
    return summary_html

def generate_report_from_runner_results(results, output_file="final_report.html"):
    """
    Generate report directly from RFT_run.py results
    
    Parameters:
    -----------
    results : dict
        Results dictionary from run_complete_test()
    output_file : str
        Output HTML file path
    """
    
    if not results.get("success", False):
        print("❌ Cannot generate report: Test was not successful")
        return
    
    if not results.get("post_analysis_success", False):
        print("❌ Cannot generate report: Post-optimization analysis failed")
        return
    
    post_results = results["post_optimization"]
    animal_requirements = results["animal_requirements"]
    
    generate_report(post_results, animal_requirements, output_file)

def print_selected_feeds(best_solution_vector, f_nd, total_cost):
    """
    Print the selected feeds for the diet recommendation
    """
    print("\n" + "="*60)
    print("🍽️  DIET RECOMMENDATION - SELECTED FEEDS")
    print("="*60)
    
    # Convert f_nd to DataFrame for easy access
    f_nd_df = pd.DataFrame(f_nd)
    
    # Get selected feeds (non-zero amounts)
    selected_feeds = []
    total_dm = 0
    
    for i, amount in enumerate(best_solution_vector):
        if amount > 0:
            feed_name = f_nd_df.iloc[i]['Fd_Name']
            feed_category = f_nd_df.iloc[i]['Fd_Category']
            feed_type = f_nd_df.iloc[i]['Fd_Type']
            feed_cost = f_nd_df.iloc[i]['Fd_Cost']
            feed_dm = f_nd_df.iloc[i]['Fd_DM']
            
            # Calculate as-fed amount
            af_amount = amount / (feed_dm / 100) if feed_dm > 0 else amount
            feed_cost_total = af_amount * feed_cost
            
            selected_feeds.append({
                'name': feed_name,
                'category': feed_category,
                'type': feed_type,
                'dm_kg': amount,
                'af_kg': af_amount,
                'dm_pct': feed_dm,
                'cost_per_kg': feed_cost,
                'total_cost': feed_cost_total
            })
            total_dm += amount
    
    # Sort by amount (highest first)
    selected_feeds.sort(key=lambda x: x['dm_kg'], reverse=True)
    
    # Print header
    print(f"{'Feed Name':<25} {'Category':<15} {'DM (kg)':<10} {'AF (kg)':<10} {'Cost ($)':<10}")
    print("-" * 70)
    
    # Print each selected feed
    for feed in selected_feeds:
        print(f"{feed['name']:<25} {feed['category']:<15} {feed['dm_kg']:<10.3f} {feed['af_kg']:<10.3f} {feed['total_cost']:<10.2f}")
    
    print("-" * 70)
    print(f"{'TOTAL':<25} {'':<15} {total_dm:<10.3f} {'':<10} {total_cost:<10.2f}")
    
    # Calculate percentages
    print(f"\n📊 DIET COMPOSITION:")
    print(f"Total DM: {total_dm:.3f} kg/day")
    print(f"Total Cost: ${total_cost:.2f}/day")
    
    # Group by category
    category_totals = {}
    for feed in selected_feeds:
        cat = feed['category']
        if cat not in category_totals:
            category_totals[cat] = {'dm': 0, 'cost': 0}
        category_totals[cat]['dm'] += feed['dm_kg']
        category_totals[cat]['cost'] += feed['total_cost']
    
    print(f"\n📈 BY CATEGORY:")
    for cat, totals in category_totals.items():
        pct = (totals['dm'] / total_dm) * 100 if total_dm > 0 else 0
        print(f"  {cat}: {totals['dm']:.3f} kg ({pct:.1f}%) - ${totals['cost']:.2f}")
    
    print("="*60)

# Run 

#if __name__ == "__main__":
