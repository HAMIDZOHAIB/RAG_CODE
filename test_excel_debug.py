"""
TEST SCRIPT - Debug Excel Plain Text Display
Tests the complete pipeline with realistic chunked data
"""

import sys
sys.path.insert(0, '/home/claude')

from excel_handler import ExcelHandler


def generate_test_data():
    """Generate realistic test data with chunked text"""
    
    # Sample 1: Short content
    short_text = """
======================================================================
CONTENT SUMMARY
======================================================================
Total Chunks: 2
Estimated Reading Time: 4 minutes
Content Organization: Divided into digestible sections
======================================================================

######################################################################
### CHUNK 1 ###
######################################################################

============================================================
WELCOME TO OUR ASSESSMENT PLATFORM
============================================================

We provide comprehensive psychometric assessment solutions for modern businesses.
Our platform helps you evaluate talent effectively and make better hiring decisions.

With over 10 years of experience, we've helped thousands of companies improve
their recruitment process and build stronger teams.

  • Psychometric assessments
  • Skill testing
  • Behavioral analysis
  • Custom reporting
  • API integrations
  • 24/7 support

============================================================
WHY CHOOSE US
============================================================

Our platform stands out because of our scientific approach and user-friendly
interface. We combine proven psychological principles with modern technology
to deliver accurate, actionable insights.

Every assessment is developed by certified psychologists and validated through
rigorous testing. Our proprietary algorithms ensure reliability and fairness.

######################################################################
### CHUNK 2 ###
######################################################################

============================================================
PRICING PLANS
============================================================

We offer flexible pricing to suit businesses of all sizes:

  • Basic Plan: $99/month
    - Up to 50 assessments per month
    - Standard reports
    - Email support
  
  • Professional: $299/month
    - Up to 200 assessments per month
    - Advanced analytics
    - Priority support
    - Custom branding
  
  • Enterprise: Custom pricing
    - Unlimited assessments
    - Dedicated account manager
    - White-label solution
    - Custom integrations

All plans include our core features, regular updates, and data security compliance.

============================================================
GET STARTED TODAY
============================================================

Ready to transform your hiring process? Sign up for a free 14-day trial
and experience the difference our platform makes.

No credit card required. Cancel anytime. Full feature access during trial.
"""

    # Sample 2: Multi-page content
    multipage_text = """
================================================================================
================================================================================
                        MULTI-PAGE WEBSITE CONTENT
================================================================================
================================================================================

Website: https://example-assessment.com
Total Pages Scraped: 3
Content Sections: pricing, features, about

NAVIGATION GUIDE:
- Search for "### HOMEPAGE ###" to find homepage content
- Search for "### PRICING PAGE ###" to find pricing information
- Search for "### FEATURES PAGE ###" to find features
- Each page is divided into CHUNKS for easy reading
- Each chunk is approximately 300 words

TIP: Use Ctrl+F (Find) to search for specific sections or keywords

================================================================================
================================================================================


################################################################################
################################################################################
###                           HOMEPAGE                                       ###
################################################################################
################################################################################
URL: https://example-assessment.com

======================================================================
CONTENT SUMMARY
======================================================================
Total Chunks: 2
Estimated Reading Time: 4 minutes
======================================================================

######################################################################
### CHUNK 1 ###
######################################################################

============================================================
TRANSFORM YOUR HIRING PROCESS
============================================================

Welcome to the future of talent assessment. Our AI-powered platform helps
you identify the best candidates faster and more accurately than ever before.

Join over 5,000 companies that trust us for their hiring needs.

  • 95% accuracy in candidate prediction
  • 60% reduction in time-to-hire
  • 40% improvement in retention rates
  • Used by Fortune 500 companies

============================================================
HOW IT WORKS
============================================================

Our platform uses cutting-edge psychometric science combined with machine
learning to evaluate candidates across multiple dimensions:

1. Cognitive Abilities - Problem-solving, logical reasoning, numerical skills
2. Personality Traits - Big Five model with industry-specific adaptations
3. Behavioral Patterns - Work style, team dynamics, leadership potential
4. Skills Assessment - Job-specific competencies and technical abilities

Results are delivered in easy-to-understand reports that help you make
confident hiring decisions.

######################################################################
### CHUNK 2 ###
######################################################################

============================================================
TRUSTED BY INDUSTRY LEADERS
============================================================

"This platform revolutionized our hiring process. We've seen a 50% reduction
in bad hires and significant improvements in team performance."
- Sarah Johnson, HR Director at TechCorp

"The insights we get are incredibly valuable. It's like having a team of
industrial psychologists working 24/7."
- Michael Chen, Talent Acquisition Lead at InnovateLabs

  • 98% customer satisfaction rate
  • 4.9/5 average rating
  • 10,000+ successful hires
  • Operating in 45 countries


################################################################################
################################################################################
###                    FEATURES PAGE                                         ###
################################################################################
################################################################################
URL: https://example-assessment.com/features
Keywords: features, capabilities

======================================================================
CONTENT SUMMARY
======================================================================
Total Chunks: 2
Estimated Reading Time: 4 minutes
======================================================================

######################################################################
### CHUNK 1 ###
######################################################################

============================================================
COMPREHENSIVE ASSESSMENT LIBRARY
============================================================

Access our extensive library of validated assessments:

  • Cognitive Tests
    - Numerical reasoning
    - Verbal reasoning
    - Abstract reasoning
    - Spatial awareness
  
  • Personality Assessments
    - Big Five personality test
    - DISC assessment
    - Myers-Briggs Type Indicator
    - Situational judgment tests
  
  • Skills Evaluations
    - Technical skills testing
    - Language proficiency
    - Software competency
    - Industry-specific knowledge

All assessments are scientifically validated and regularly updated.

============================================================
ADVANCED ANALYTICS
============================================================

Turn data into insights with our powerful analytics dashboard:

  • Real-time candidate scoring
  • Comparative analysis across candidates
  • Predictive success modeling
  • Team compatibility analysis
  • Custom report generation
  • Export to multiple formats (PDF, Excel, CSV)

Track hiring metrics and ROI with built-in analytics tools.

######################################################################
### CHUNK 2 ###
######################################################################

============================================================
SEAMLESS INTEGRATIONS
============================================================

Connect with your existing HR tech stack:

  • Applicant Tracking Systems (ATS)
    - Greenhouse, Lever, Workday, BambooHR
  
  • HRIS Platforms
    - SAP SuccessFactors, Oracle HCM, Workday
  
  • Communication Tools
    - Slack, Microsoft Teams, Email
  
  • Video Interview Platforms
    - Zoom, HireVue, Spark Hire

API access available for custom integrations.

============================================================
SECURITY & COMPLIANCE
============================================================

Your data is protected by enterprise-grade security:

  • SOC 2 Type II certified
  • GDPR compliant
  • ISO 27001 certified
  • AES-256 encryption
  • Regular security audits
  • Data residency options


################################################################################
################################################################################
###                    PRICING PAGE                                          ###
################################################################################
################################################################################
URL: https://example-assessment.com/pricing
Keywords: pricing, plans

======================================================================
CONTENT SUMMARY
======================================================================
Total Chunks: 1
Estimated Reading Time: 2 minutes
======================================================================

######################################################################
### CHUNK 1 ###
######################################################################

============================================================
TRANSPARENT PRICING
============================================================

Choose the plan that fits your needs:

  • Starter - $149/month
    - 100 assessments/month
    - All assessment types
    - Basic analytics
    - Email support
    - 5 user accounts
  
  • Growth - $399/month
    - 500 assessments/month
    - Advanced analytics
    - Priority support
    - 15 user accounts
    - Custom branding
    - API access
  
  • Enterprise - Custom pricing
    - Unlimited assessments
    - White-label solution
    - Dedicated success manager
    - Custom integrations
    - SLA guarantees
    - Unlimited users

All plans include:
  • Free 14-day trial
  • No setup fees
  • Cancel anytime
  • Regular updates
  • Data export
  • Training resources

Volume discounts available for annual commitments.

============================================================
CALCULATE YOUR ROI
============================================================

Average customer results:
  • 60% faster hiring process
  • 40% better quality of hire
  • $50,000 saved per bad hire avoided
  • 3-month payback period

Try our ROI calculator to see your potential savings.
"""

    # Sample 3: Error case (empty text)
    empty_text = "No content extracted"
    
    # Create test results
    test_results = [
        {
            'website_link': 'https://example-assessment.com',
            'title': 'Leading Assessment Platform - Transform Your Hiring',
            'metadata': 'Comprehensive psychometric assessment solutions for modern businesses. Trusted by 5,000+ companies worldwide.',
            'plain_text': short_text
        },
        {
            'website_link': 'https://example-assessment.com/multi',
            'title': 'Complete Platform Overview - Features, Pricing, and More',
            'metadata': 'Explore our platform with detailed information on features, pricing plans, and customer success stories. | Scraped 3 pages | Sections: pricing, features, about',
            'plain_text': multipage_text
        },
        {
            'website_link': 'https://example-failed.com',
            'title': 'Error',
            'metadata': 'Failed to scrape',
            'plain_text': empty_text
        }
    ]
    
    return test_results


def main():
    """Run comprehensive test"""
    print("\n" + "="*80)
    print("EXCEL EXPORT TEST - CHUNKED TEXT DATA")
    print("="*80)
    
    # Initialize handler
    handler = ExcelHandler()
    
    # Generate test data
    print("\n📝 Generating test data with chunked text...")
    test_data = generate_test_data()
    
    print(f"   ✅ Generated {len(test_data)} test records")
    for i, record in enumerate(test_data, 1):
        text_len = len(record['plain_text'])
        print(f"      {i}. {record['website_link'][:50]}... ({text_len:,} chars)")
    
    # Export with debug mode
    print("\n" + "="*80)
    print("EXPORTING TO EXCEL (DEBUG MODE)")
    print("="*80)
    
    output_file = handler.export_to_excel(
        test_data, 
        filename="test_chunked_data.xlsx",
        debug=True  # Enable debugging
    )
    
    if output_file:
        print("\n" + "="*80)
        print("✅ EXPORT SUCCESSFUL")
        print("="*80)
        print(f"\n📁 File created: {output_file}")
        
        # Verify the file
        print("\n" + "="*80)
        print("VERIFYING EXCEL FILE")
        print("="*80)
        
        import pandas as pd
        df = pd.read_excel(output_file, engine='openpyxl')
        
        print(f"\n📊 File Statistics:")
        print(f"   Total rows: {len(df)}")
        print(f"   Columns: {list(df.columns)}")
        
        print(f"\n📝 Plain Text Column Analysis:")
        for idx, row in df.iterrows():
            text = row['plain_text']
            text_len = len(text) if isinstance(text, str) else 0
            preview = text[:100] if isinstance(text, str) else 'N/A'
            
            print(f"\n   Row {idx + 1}:")
            print(f"      URL: {row['website_link'][:50]}...")
            print(f"      Plain text length: {text_len:,} chars")
            print(f"      Preview: {preview}...")
            
            # Check for chunk markers
            if isinstance(text, str):
                has_chunks = '### CHUNK' in text
                has_headers = '============' in text
                has_summary = 'CONTENT SUMMARY' in text
                
                print(f"      Contains chunks: {'✅' if has_chunks else '❌'}")
                print(f"      Contains headers: {'✅' if has_headers else '❌'}")
                print(f"      Contains summary: {'✅' if has_summary else '❌'}")
        
        print("\n" + "="*80)
        print("INSTRUCTIONS TO VIEW IN EXCEL")
        print("="*80)
        print(f"""
1. Open the file: {output_file}

2. Click on the 'plain_text' column (column D)

3. Adjust column width:
   - Right-click column header 'D'
   - Select 'Column Width'
   - Enter: 120
   - Click OK

4. Enable text wrapping:
   - With column D selected
   - Go to Home tab
   - Click 'Wrap Text'

5. Expand row height:
   - Click on a cell in plain_text column
   - The row should auto-expand to show content

6. Read the content:
   - Scroll through the cell
   - Or double-click to edit mode to see full text
   - Look for chunk markers: ### CHUNK 1 ###

7. Search for specific sections:
   - Press Ctrl+F
   - Search for: "### CHUNK 1 ###"
   - Or search for: "PRICING"
   - Navigate through results
        """)
        
        print("\n" + "="*80)
        print("TEST COMPLETE")
        print("="*80)
        
    else:
        print("\n" + "="*80)
        print("❌ EXPORT FAILED")
        print("="*80)


if __name__ == "__main__":
    main()