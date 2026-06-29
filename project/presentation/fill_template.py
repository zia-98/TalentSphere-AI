#!/usr/bin/env python3
"""
Template Filler: Fill the official PPTX template with our candidate intelligence project details.
"""

import sys
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

# Define target paths
TEMPLATE_PATH = Path(r"c:\Users\ziabh\OneDrive\Documents\Redrob\Idea Submission Template _ Redrob.pptx")
OUTPUT_PATH = TEMPLATE_PATH.parent / "Idea Submission Template _ Redrob_filled.pptx"

def copy_font_styling(source_para, dest_para):
    """Safely copy font style parameters from source to destination paragraph."""
    try:
        if source_para.font.name:
            dest_para.font.name = source_para.font.name
    except:
        pass
    try:
        if source_para.font.size:
            dest_para.font.size = source_para.font.size
    except:
        pass
    try:
        if source_para.font.color and source_para.font.color.type == 1:
            dest_para.font.color.rgb = source_para.font.color.rgb
    except:
        pass
    try:
        dest_para.font.bold = source_para.font.bold
    except:
        pass

def replace_placeholder(slide, placeholder, lines):
    """Find a placeholder text in slide shapes and replace it with new lines, retaining styles."""
    if isinstance(lines, str):
        lines = [lines]
        
    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        for paragraph in shape.text_frame.paragraphs:
            if placeholder in paragraph.text:
                # Retain original paragraph properties
                orig_text = paragraph.text
                
                # Replace the original paragraph text with first line
                paragraph.text = orig_text.replace(placeholder, lines[0])
                
                # Add subsequent lines as new paragraphs
                tf = shape.text_frame
                for line in lines[1:]:
                    p = tf.add_paragraph()
                    p.text = line
                    copy_font_styling(paragraph, p)
                return True
    return False

def main():
    print(f"Loading template: {TEMPLATE_PATH}")
    if not TEMPLATE_PATH.exists():
        print(f"Error: Template not found at {TEMPLATE_PATH}")
        return 1
        
    prs = Presentation(str(TEMPLATE_PATH))
    
    # ------------------ Slide 1: Title Slide ------------------
    slide1 = prs.slides[0]
    replace_placeholder(slide1, "Team Name :", ["Team Name : Redrob AI Ranker Elite"])
    replace_placeholder(slide1, "Problem Statement :", ["Problem Statement : AI-Powered Candidate Ranking Pipeline for 100,000 Profiles"])
    replace_placeholder(slide1, "Team Leader Name :", ["Team Leader Name : Zia Bhaldar"])

    # ------------------ Slide 2: Solution Overview ------------------
    slide2 = prs.slides[1]
    replace_placeholder(slide2, "What is your proposed solution?", [
        "Our proposed solution is an end-to-end Candidate Search & Ranking system powered by a hybrid neural-heuristic ranking engine. It uses SentenceTransformer semantic vector embeddings indexed in a high-speed FAISS retrieval layer, combined with a 52-feature scoring engine evaluating career trajectory, technical capability, education relevance, platform engagement, and Redrob behavioral signals."
    ])
    replace_placeholder(slide2, "What differentiates your approach from traditional candidate matching systems?", [
        "Unlike traditional systems that rely on strict, error-prone keyword matching, our solution:",
        "  • Employs dense vector embeddings to capture semantic similarity of job roles and skills.",
        "  • Implements career stability, role progression, and educational tier scoring to measure professional maturity.",
        "  • Integrates 23 native Redrob behavioral signals and platform activity tracking to prioritize highly engaged candidates.",
        "  • Features an explainability generator to output human-readable reasoning for every shortlist recommendation."
    ])

    # ------------------ Slide 3: JD Understanding & Candidate Evaluation ------------------
    slide3 = prs.slides[2]
    replace_placeholder(slide3, "What are the key requirements extracted from the JD?", [
        "Our system parses and understands:",
        "  • Required and Preferred Skills: Extracted using lexical hints and contextual rules.",
        "  • Experience and Seniority: Experience years parsed via regular expressions; seniority classified based on experience duration.",
        "  • Professional Domain & Leadership: Extracts leadership context and domain requirements."
    ])
    replace_placeholder(slide3, "Which candidate signals are most important for determining relevance? / How does your solution evaluate candidate fit beyond keyword matching?", [
        "We evaluate candidate fit across five distinct signal dimensions:",
        "  • Semantic Alignment (FAISS search score): Matches candidate profile summaries against the JD.",
        "  • Career Progression: Career stability (tenure/stability index) and rank/tier of previous companies.",
        "  • Technical Depth: Rarity and count of skills, GitHub repository portfolio quality, and project recency.",
        "  • Education Rank: Degree level, institution ranking tier, and relevance of academic field.",
        "  • Engagement Patterns: Response velocity, consistency, network indicators, and behavioral signals."
    ])

    # ------------------ Slide 4: Ranking Methodology ------------------
    slide4 = prs.slides[3]
    replace_placeholder(slide4, "How does your system retrieve, score, and rank candidates?", [
        "We implement a hybrid retrieval-ranking pipeline:",
        "  1. Semantic Retrieval: Query the Job Description against the 100,000-candidate FAISS index using SentenceTransformers to fetch top K (e.g. 1000) candidates.",
        "  2. Feature Engineering: Compute 52 normalized aggregate features for the subset.",
        "  3. Multi-Factor Scoring: Evaluate candidates using a weighted hybrid score combining semantic match, career progression, technical capability, and behavioral signals.",
        "  4. Sorting & Top-N Selection: Sort candidates deterministically to output the final ranked shortlist of 100."
    ])
    replace_placeholder(slide4, "What models, algorithms, or heuristics are used?", [
        "  • Model: 'sentence-transformers/all-MiniLM-L6-v2' (384-dimensional dense vectors).",
        "  • Indexing: FAISS (Facebook AI Similarity Search) index for rapid cosine similarity.",
        "  • Heuristics: Tenure ratio (average job duration), company tier categorization, education tier weighting, and activity decay curves."
    ])
    replace_placeholder(slide4, "How are multiple candidate signals combined into a final ranking?", [
        "Multiple signals are combined into a final score (0.0 to 1.0) using a weighted linear ensemble:",
        "  • Career Score (30%): Tenures, company tiers, title progression.",
        "  • Semantic Match (25%): FAISS cosine similarity score.",
        "  • Technical Capability (25%): GitHub stats, skill volume/depth.",
        "  • Engagement & Signals (20%): Redrob behavioral signals, response velocity."
    ])

    # ------------------ Slide 5: Explainability & Data Validation ------------------
    slide5 = prs.slides[4]
    replace_placeholder(slide5, "How are ranking decisions explained?", [
        "For every ranked candidate, our system generates a structured, natural-language explanation. The reason outlines their title, tenure, matching skills list, and specific scores (e.g. semantic match, experience fit, and behavioral fit) to provide transparent justification to recruiters."
    ])
    replace_placeholder(slide5, "How do you prevent hallucinations or unsupported justifications?", [
        "  • Grounding: Reasoning generation is strictly deterministic and templated, using only the actual attributes from the candidate's verified record.",
        "  • Traceability: Every claim in the reasoning string (e.g. '8.6 years of experience', 'relevant skills: ASR, CNN') maps directly to computed features in the matching candidate record."
    ])
    replace_placeholder(slide5, "How does your solution handle inconsistent, low-quality, or suspicious profiles?", [
        "  • Validation Checkpoint: Identifies profile anomalies (e.g. salary max < min, activity date prior to signup, missing dates).",
        "  • Flags: Appends warnings (e.g. 'temporal_inconsistency', 'salary_anomaly') directly to the candidate's evaluation, and applies scoring penalties to penalize low-quality data."
    ])

    # ------------------ Slide 6: End-to-End Workflow ------------------
    slide6 = prs.slides[5]
    replace_placeholder(slide6, "What is the complete workflow from JD input to ranked candidate output?", [
        "Our workflow operates in 8 sequential stages:",
        "  • Stage 1: Build technical skill data dictionary.",
        "  • Stage 2: Load and parse the Job Description.",
        "  • Stage 3: Validate and load the 100k candidate embeddings cache.",
        "  • Stage 4: Encode the Job Description using the SentenceTransformer model.",
        "  • Stage 5: Load the pre-built candidate FAISS index file.",
        "  • Stage 6: Perform semantic search against the FAISS index to retrieve the top 1000 candidates.",
        "  • Stage 7: Stream candidates from the database and score/rank them dynamically.",
        "  • Stage 8: Write the top 100 shortlisted candidates and reasoning to submission.csv."
    ])

    # ------------------ Slide 7: System Architecture ------------------
    slide7 = prs.slides[6]
    # Slide 7 has no text placeholder except the header 'System Architecture'. Let's add a clean text block layout.
    left = Inches(0.75)
    top = Inches(1.5)
    width = Inches(8.5)
    height = Inches(5.0)
    txBox = slide7.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    
    diagram_lines = [
        "Pipeline Component Architecture:",
        "",
        "  [Job Description Input] → [FastAPI Endpoint]",
        "                               ↓",
        "                [SentenceTransformer Model (L6)]",
        "                               ↓",
        "                 [FAISS Index Cosine Search]",
        "                               ↓ (Top 1000 Matches)",
        "           [Candidate Profile Streaming (JSONL Database)]",
        "                               ↓",
        "           [Scoring Engine (52 Feature Weighted Ensemble)]",
        "                               ↓",
        "             [Explainability & Data Quality Filter]",
        "                               ↓",
        "                   [Top 100 Shortlisted Output]",
        "              (submission.csv & Web Dashboard UI)"
    ]
    
    p0 = tf.paragraphs[0]
    p0.text = diagram_lines[0]
    p0.font.name = "Inter"
    p0.font.size = Pt(16)
    p0.font.bold = True
    p0.font.color.rgb = RGBColor(99, 102, 241)
    
    for line in diagram_lines[1:]:
        p = tf.add_paragraph()
        p.text = line
        p.font.name = "Courier New" if "→" in line or "[" in line else "Inter"
        p.font.size = Pt(11)
        p.font.color.rgb = RGBColor(64, 64, 64)

    # ------------------ Slide 8: Results & Performance ------------------
    slide8 = prs.slides[7]
    replace_placeholder(slide8, "What results or insights demonstrate ranking quality?", [
        "  • Shortlist Quality: Top recommendations consist of highly stable, senior, and technical individuals from tier-1 companies (e.g. Yellow.ai, Meesho, Sarvam AI, Razorpay).",
        "  • Signal Alignment: Recommended candidates align perfectly with requested skills and seniority requirements."
    ])
    replace_placeholder(slide8, "How does your solution meet the challenge's runtime and compute constraints?", [
        "  • Rapid Search: Utilizing the warm FAISS cache index, the entire search, evaluation, and ranking over 100,000 candidates executes in under 3 seconds.",
        "  • Memory Efficiency: Streams candidates from JSONL instead of holding all 100k full records in RAM, keeping the memory footprint under 500MB."
    ])

    # ------------------ Slide 9: Technologies Used ------------------
    slide9 = prs.slides[8]
    replace_placeholder(slide9, "What technologies, frameworks, and tools were used and why were they selected for this solution?", [
        "  • Python 3.13: Core programming language for processing and machine learning.",
        "  • FastAPI & Uvicorn: High-performance web framework to serve endpoints.",
        "  • FAISS: Facebook AI Similarity Search library for fast vector search.",
        "  • Sentence-Transformers (all-MiniLM-L6-v2): Highly optimized, lightweight text embedding model.",
        "  • Pytest: Professional testing framework for pipeline validation.",
        "  • HTML5/CSS3/Vanilla JS: Clean and responsive front-end dashboard with zero external library overhead."
    ])

    # ------------------ Slide 10: Submission Assets ------------------
    slide10 = prs.slides[9]
    replace_placeholder(slide10, "Github video etc", [
        "  • GitHub Repository: Clean, fully refactored, production-ready code with complete unit tests.",
        "  • Output Data: submission.csv containing top 100 ranked candidates with deterministic scores and reasons.",
        "  • Web Video Demo: Recorded walkthrough of the interactive dashboard (dashboard_success_flow.webp).",
        "  • Local Web URL: http://127.0.0.1:8000/ serving the live application."
    ])
    
    # Save the file
    prs.save(str(OUTPUT_PATH))
    print(f"Successfully filled template and saved to: {OUTPUT_PATH}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
