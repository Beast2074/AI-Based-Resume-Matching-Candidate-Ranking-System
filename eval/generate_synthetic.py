"""
Generate 30 synthetic resumes across 3 job descriptions and 4 document layouts.
Includes ground-truth annotations in eval/gold.json with true skills, true experience years,
relevance tiers, and deliberate edge-case traps (synonyms, overlapping jobs, Present dates, gaps).
"""

import json
import os
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

from faker import Faker
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import pymupdf

# Import parsing helper for consistent total_years math
from app.services.parsing import calculate_total_years

fake = Faker()
Faker.seed(42)
random.seed(42)

CURRENT_YEAR = datetime.now().year
CURRENT_MONTH = datetime.now().month

LAYOUTS = ["single_column_pdf", "two_column_pdf", "table_docx", "plain_docx"]

def make_date_tuple(start_y: int, start_m: int, end_y: Optional[int], end_m: Optional[int]) -> Tuple[datetime, datetime]:
    start = datetime(start_y, start_m, 1)
    if end_y is None:
        end = datetime(CURRENT_YEAR, CURRENT_MONTH, 1)
    else:
        end = datetime(end_y, end_m or 12, 1)
    return start, end

def format_date_str(start_d: datetime, end_d: datetime, is_present: bool = False, format_style: str = "mon_yyyy") -> str:
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    s_mon = month_names[start_d.month - 1]
    
    if is_present:
        end_str = "Present"
    else:
        e_mon = month_names[end_d.month - 1]
        end_str = f"{e_mon} {end_d.year}"

    if format_style == "mon_yyyy":
        return f"{s_mon} {start_d.year} - {end_str}"
    elif format_style == "slash":
        e_slash = "Present" if is_present else f"{end_d.month:02d}/{end_d.year}"
        return f"{start_d.month:02d}/{start_d.year} - {e_slash}"
    elif format_style == "year_only":
        e_yr = "Present" if is_present else f"{end_d.year}"
        return f"{start_d.year} - {e_yr}"
    return f"{s_mon} {start_d.year} - {end_str}"


def get_resume_specs() -> List[Dict[str, Any]]:
    """Define the 30 resumes specifications."""
    specs = []

    # -------------------------------------------------------------
    # 1. Java Backend Engineer (10 resumes: 3 strong, 3 medium, 2 weak, 1 irrelevant, 1 keyword-stuffed)
    # -------------------------------------------------------------
    # Java 1: Strong (Tier 3) - single_column_pdf (Has k8s synonym, Docker, Spring Boot, Postgres)
    specs.append({
        "id": "java_01_strong",
        "jd": "java_backend",
        "tier": 3,
        "name": "Marcus Vance",
        "roles": [
            {
                "title": "Lead Java Developer",
                "company": "Nexus Financial Systems",
                "dates": make_date_tuple(2023, 1, None, None),
                "is_present": True,
                "format": "mon_yyyy",
                "bullets": [
                    "Engineered distributed REST microservices in Java 17 using Spring Boot and Hibernate.",
                    "Configured Kafka cluster topics for real-time transaction processing.",
                    "Orchestrated container deployments on k8s (Kubernetes) and optimized Postgres SQL queries.",
                    "Integrated Redis distributed cache achieving 40% reduction in latency."
                ]
            },
            {
                "title": "Backend Software Engineer",
                "company": "Apex Cloud Technologies",
                "dates": make_date_tuple(2020, 3, 2022, 12),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Developed backend microservices using Java, Spring Boot, and PostgreSQL.",
                    "Built containerized services with Docker and deployed to AWS EC2.",
                    "Implemented unit testing with JUnit and Mockito achieving 90% coverage."
                ]
            }
        ],
        "skills_list": ["Java", "Spring Boot", "Microservices", "PostgreSQL", "SQL", "Docker", "Kubernetes", "Kafka", "Redis", "AWS", "JUnit", "REST"],
        "true_skills": ["Java", "Spring Boot", "Microservices", "PostgreSQL", "SQL", "Docker", "Kubernetes", "Kafka", "Redis", "AWS", "Unit Testing", "REST"],
        "degree": "Bachelor of Science in Computer Science",
        "education": "BS in Computer Science, Georgia Institute of Technology, 2016 - 2020",
        "traps": ["synonym_k8s_postgres", "present_date"]
    })

    # Java 2: Strong (Tier 3) - two_column_pdf (Overlapping jobs trap)
    specs.append({
        "id": "java_02_strong",
        "jd": "java_backend",
        "tier": 3,
        "name": "Elena Rostova",
        "roles": [
            {
                "title": "Senior Backend Engineer",
                "company": "Hyperion Labs",
                "dates": make_date_tuple(2021, 6, 2025, 6),
                "is_present": False,
                "format": "slash",
                "bullets": [
                    "Architected high-throughput REST APIs and microservices using Java and Spring Boot.",
                    "Designed relational schema in PostgreSQL and MySQL with complex SQL optimizations.",
                    "Automated CI/CD pipelines and deployed microservices into Docker containers."
                ]
            },
            {
                "title": "Java Consultant (Concurrent Role)",
                "company": "Vanguard Solutions",
                "dates": make_date_tuple(2022, 1, 2023, 1), # Overlapping by 12 months with Hyperion Labs!
                "is_present": False,
                "format": "slash",
                "bullets": [
                    "Consulted on enterprise Java architecture and microservices design.",
                    "Conducted comprehensive unit testing with Mockito."
                ]
            },
            {
                "title": "Software Engineer",
                "company": "Crestview Media",
                "dates": make_date_tuple(2019, 1, 2021, 5),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Developed RESTful endpoints in Java with Hibernate and MySQL.",
                    "Maintained AWS cloud infrastructure and Docker setups."
                ]
            }
        ],
        "skills_list": ["Java", "Spring Boot", "Hibernate", "Microservices", "PostgreSQL", "MySQL", "SQL", "Docker", "AWS", "CI/CD", "Unit Testing", "REST"],
        "true_skills": ["Java", "Spring Boot", "Hibernate", "Microservices", "PostgreSQL", "MySQL", "SQL", "Docker", "AWS", "CI/CD", "Unit Testing", "REST"],
        "degree": "Bachelor of Science in Software Engineering",
        "education": "BS in Software Engineering, Purdue University, 2015 - 2019",
        "traps": ["overlapping_jobs"]
    })

    # Java 3: Strong (Tier 3) - table_docx (Short role under one year trap)
    specs.append({
        "id": "java_03_strong",
        "jd": "java_backend",
        "tier": 3,
        "name": "David Chen",
        "roles": [
            {
                "title": "Senior Java Architect",
                "company": "OmniCorp Global",
                "dates": make_date_tuple(2023, 7, None, None),
                "is_present": True,
                "format": "mon_yyyy",
                "bullets": [
                    "Designed scalable microservices with Java, Spring Boot, and Apache Kafka.",
                    "Managed PostgreSQL clusters and Redis caching layers.",
                    "Automated deployments using Kubernetes and Docker."
                ]
            },
            {
                "title": "Backend Engineer (Contract)",
                "company": "Velocity Tech",
                "dates": make_date_tuple(2023, 1, 2023, 6), # Role under 1 year (6 months)
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Delivered high-performance REST APIs in Java with Spring Boot."
                ]
            },
            {
                "title": "Software Developer",
                "company": "DataStream Inc",
                "dates": make_date_tuple(2020, 1, 2022, 12),
                "is_present": False,
                "format": "year_only",
                "bullets": [
                    "Implemented RESTful web services in Java and SQL database routines.",
                    "Containerized internal services with Docker and wrote unit tests with JUnit."
                ]
            }
        ],
        "skills_list": ["Java", "Spring Boot", "Microservices", "Kafka", "PostgreSQL", "SQL", "Redis", "Docker", "Kubernetes", "REST", "Unit Testing"],
        "true_skills": ["Java", "Spring Boot", "Microservices", "Kafka", "PostgreSQL", "SQL", "Redis", "Docker", "Kubernetes", "REST", "Unit Testing"],
        "degree": "Bachelor of Science in Computer Science",
        "education": "BS in Computer Science, University of Washington, 2016 - 2020",
        "traps": ["short_role_under_one_year", "present_date"]
    })

    # Java 4: Medium (Tier 2) - plain_docx (Career gap trap)
    specs.append({
        "id": "java_04_medium",
        "jd": "java_backend",
        "tier": 2,
        "name": "Sarah Jenkins",
        "roles": [
            {
                "title": "Java Developer",
                "company": "Krypton Web Solutions",
                "dates": make_date_tuple(2023, 1, 2025, 12),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Developed backend features using Java and Spring Boot.",
                    "Wrote SQL queries for PostgreSQL and maintained REST services.",
                    "Used Docker for local development."
                ]
            },
            # Career gap from 2021-06 to 2022-12 (18 months gap)
            {
                "title": "Junior Backend Developer",
                "company": "BlueShift Data",
                "dates": make_date_tuple(2020, 1, 2021, 6),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Maintained Java legacy applications and MySQL database queries."
                ]
            }
        ],
        "skills_list": ["Java", "Spring Boot", "PostgreSQL", "MySQL", "SQL", "REST", "Docker"],
        "true_skills": ["Java", "Spring Boot", "PostgreSQL", "MySQL", "SQL", "REST", "Docker"],
        "degree": "Bachelor of Arts in Information Technology",
        "education": "BA in Information Technology, Ohio State University, 2016 - 2020",
        "traps": ["career_gap"]
    })

    # Java 5: Medium (Tier 2) - single_column_pdf (Missing Kafka and Kubernetes)
    specs.append({
        "id": "java_05_medium",
        "jd": "java_backend",
        "tier": 2,
        "name": "Brian O'Connor",
        "roles": [
            {
                "title": "Backend Java Programmer",
                "company": "Catalyst Software",
                "dates": make_date_tuple(2021, 3, 2024, 9),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Created RESTful microservices in Java with Spring Boot.",
                    "Created SQL schemas and stored procedures in PostgreSQL.",
                    "Built Docker container images for microservice distribution."
                ]
            }
        ],
        "skills_list": ["Java", "Spring Boot", "Microservices", "PostgreSQL", "SQL", "Docker", "REST"],
        "true_skills": ["Java", "Spring Boot", "Microservices", "PostgreSQL", "SQL", "Docker", "REST"],
        "degree": "Bachelor of Science in Computer Science",
        "education": "BS in Computer Science, University of Illinois, 2017 - 2021",
        "traps": []
    })

    # Java 6: Medium (Tier 2) - two_column_pdf (C++ and Java background)
    specs.append({
        "id": "java_06_medium",
        "jd": "java_backend",
        "tier": 2,
        "name": "Kavita Patel",
        "roles": [
            {
                "title": "Software Systems Engineer",
                "company": "AeroTech Dynamics",
                "dates": make_date_tuple(2021, 1, 2024, 6),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Developed backend components using Java and C++.",
                    "Built RESTful interfaces and handled PostgreSQL data models.",
                    "Maintained Docker containers and Git repositories."
                ]
            }
        ],
        "skills_list": ["Java", "C++", "PostgreSQL", "SQL", "REST", "Docker", "Git"],
        "true_skills": ["Java", "C++", "PostgreSQL", "SQL", "REST", "Docker", "Git"],
        "degree": "Bachelor of Science in Electrical Engineering",
        "education": "BS in Electrical Engineering, Penn State, 2016 - 2020",
        "traps": []
    })

    # Java 7: Weak (Tier 1) - table_docx (Only 1 year experience, missing Spring Boot & Docker)
    specs.append({
        "id": "java_07_weak",
        "jd": "java_backend",
        "tier": 1,
        "name": "Tyler Brooks",
        "roles": [
            {
                "title": "Junior Java Associate",
                "company": "Apex Digital",
                "dates": make_date_tuple(2024, 1, 2025, 2),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Wrote core Java functions and basic SQL queries."
                ]
            }
        ],
        "skills_list": ["Java", "SQL", "Git"],
        "true_skills": ["Java", "SQL", "Git"],
        "degree": "Associate Degree in Computer Programming",
        "education": "AS in Computer Programming, Austin Community College, 2022 - 2024",
        "traps": ["short_experience"]
    })

    # Java 8: Weak (Tier 1) - plain_docx (TRAP: JavaScript engineer applying for Java backend!)
    specs.append({
        "id": "java_08_weak",
        "jd": "java_backend",
        "tier": 1,
        "name": "Jason Miller",
        "roles": [
            {
                "title": "Full Stack Developer",
                "company": "PixelCraft Studios",
                "dates": make_date_tuple(2021, 1, 2024, 1),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Developed web applications using JavaScript and Node.js.",
                    "Wrote REST APIs in Express and configured MongoDB databases.",
                    "Used Docker for containerized deployment."
                ]
            }
        ],
        "skills_list": ["JavaScript", "Node.js", "MongoDB", "REST", "Docker", "HTML", "CSS"],
        "true_skills": ["JavaScript", "Node.js", "MongoDB", "REST", "Docker", "HTML", "CSS"],
        "degree": "Bachelor of Arts in Web Design",
        "education": "BA in Web Design, San Jose State University, 2017 - 2021",
        "traps": ["java_vs_javascript_trap"]
    })

    # Java 9: Irrelevant (Tier 0) - single_column_pdf (Marketing & Sales Manager)
    specs.append({
        "id": "java_09_irrelevant",
        "jd": "java_backend",
        "tier": 0,
        "name": "Chloe Adams",
        "roles": [
            {
                "title": "Digital Marketing Strategist",
                "company": "Elevate Brand Agency",
                "dates": make_date_tuple(2020, 2, 2024, 8),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Managed social media ad campaigns and Google SEO analytics.",
                    "Increased email campaign open rate by 35% through A/B testing.",
                    "Led cross-functional creative team of copywriters and graphic designers."
                ]
            }
        ],
        "skills_list": ["SEO", "Content Marketing", "Social Media", "Google Analytics", "Email Marketing", "Brand Strategy"],
        "true_skills": ["Agile"],
        "degree": "Bachelor of Science in Marketing",
        "education": "BS in Marketing, Boston University, 2016 - 2020",
        "traps": ["completely_irrelevant"]
    })

    # Java 10: Keyword-stuffed (Tier 1) - two_column_pdf (Skills dump with no supporting experience)
    specs.append({
        "id": "java_10_keyword_stuffed",
        "jd": "java_backend",
        "tier": 1,
        "name": "Arthur Pendelton",
        "roles": [
            {
                "title": "Office IT Assistant",
                "company": "Metro Logistics",
                "dates": make_date_tuple(2021, 1, 2024, 1),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Provided technical desktop support and replaced printers.",
                    "Assisted administrative personnel with Windows workstation setup and software installs."
                ]
            }
        ],
        # Stuffed with every single Java requirement in skills section:
        "skills_list": ["Java", "Spring Boot", "Microservices", "Hibernate", "PostgreSQL", "SQL", "Docker", "Kubernetes", "Kafka", "Redis", "AWS", "CI/CD", "JUnit", "REST"],
        "true_skills": ["Java", "Spring Boot", "Microservices", "Hibernate", "PostgreSQL", "SQL", "Docker", "Kubernetes", "Kafka", "Redis", "AWS", "CI/CD", "Unit Testing", "REST"],
        "degree": "High School Diploma",
        "education": "Lincoln High School, 2016 - 2020",
        "traps": ["keyword_stuffed_skills_dump"]
    })

    # -------------------------------------------------------------
    # 2. Data Scientist (10 resumes: 3 strong, 3 medium, 2 weak, 1 irrelevant, 1 keyword-stuffed)
    # -------------------------------------------------------------
    # DS 1: Strong (Tier 3) - table_docx (Present date, PyTorch, Airflow, scikit-learn)
    specs.append({
        "id": "ds_01_strong",
        "jd": "data_scientist",
        "tier": 3,
        "name": "Dr. Aris Thorne",
        "roles": [
            {
                "title": "Senior Data Scientist",
                "company": "Cortex AI Innovations",
                "dates": make_date_tuple(2022, 3, None, None),
                "is_present": True,
                "format": "mon_yyyy",
                "bullets": [
                    "Engineered end-to-end Machine Learning pipelines using Python, Pandas, and scikit-learn.",
                    "Trained Deep Learning NLP transformer models with PyTorch for sentiment analysis.",
                    "Orchestrated distributed ETL workflows using Apache Airflow and Docker.",
                    "Queried petabyte-scale data lakes with advanced SQL."
                ]
            },
            {
                "title": "Machine Learning Researcher",
                "company": "BioInformatics Core",
                "dates": make_date_tuple(2020, 1, 2022, 2),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Developed statistical models and hypothesis tests using NumPy and Pandas.",
                    "Created interactive analytical dashboards with Tableau."
                ]
            }
        ],
        "skills_list": ["Python", "Machine Learning", "Deep Learning", "NLP", "PyTorch", "scikit-learn", "Pandas", "NumPy", "SQL", "Airflow", "Docker", "Tableau"],
        "true_skills": ["Python", "Machine Learning", "Deep Learning", "NLP", "PyTorch", "scikit-learn", "Pandas", "NumPy", "SQL", "Airflow", "Docker", "Tableau"],
        "degree": "PhD in Computer Science & Applied Statistics",
        "education": "PhD in Computer Science, Stanford University, 2016 - 2020",
        "traps": ["present_date"]
    })

    # DS 2: Strong (Tier 3) - plain_docx (Overlapping jobs, Spark, PyTorch)
    specs.append({
        "id": "ds_02_strong",
        "jd": "data_scientist",
        "tier": 3,
        "name": "Maya Lin",
        "roles": [
            {
                "title": "Staff Data Scientist",
                "company": "Aura Financial",
                "dates": make_date_tuple(2022, 1, 2025, 4),
                "is_present": False,
                "format": "slash",
                "bullets": [
                    "Architected predictive Machine Learning models with scikit-learn and Python.",
                    "Processed massive datasets using Apache Spark and SQL.",
                    "Built feature stores using Pandas and NumPy."
                ]
            },
            {
                "title": "Data Science Fellow (Concurrent Project)",
                "company": "Data For Good Initiative",
                "dates": make_date_tuple(2022, 6, 2023, 6), # Overlapping by 12 months
                "is_present": False,
                "format": "slash",
                "bullets": [
                    "Implemented Deep Learning NLP classification in PyTorch."
                ]
            },
            {
                "title": "Quantitative Analyst",
                "company": "Apex Capital",
                "dates": make_date_tuple(2019, 6, 2021, 12),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Built statistical models in Python with NumPy and SQL databases."
                ]
            }
        ],
        "skills_list": ["Python", "Machine Learning", "Deep Learning", "NLP", "PyTorch", "scikit-learn", "Pandas", "NumPy", "SQL", "Spark"],
        "true_skills": ["Python", "Machine Learning", "Deep Learning", "NLP", "PyTorch", "scikit-learn", "Pandas", "NumPy", "SQL", "Spark"],
        "degree": "Master of Science in Data Science",
        "education": "MS in Data Science, Columbia University, 2017 - 2019",
        "traps": ["overlapping_jobs"]
    })

    # DS 3: Strong (Tier 3) - single_column_pdf (TensorFlow, Docker, Airflow)
    specs.append({
        "id": "ds_03_strong",
        "jd": "data_scientist",
        "tier": 3,
        "name": "Julian Weber",
        "roles": [
            {
                "title": "Lead Machine Learning Engineer",
                "company": "Synthetix Bio",
                "dates": make_date_tuple(2021, 6, 2025, 1),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Trained predictive machine learning models in Python using scikit-learn and TensorFlow.",
                    "Automated training and deployment with Apache Airflow and Docker.",
                    "Conducted feature extraction on relational SQL databases with Pandas and NumPy."
                ]
            },
            {
                "title": "Data Analyst",
                "company": "HealthMetrics",
                "dates": make_date_tuple(2020, 1, 2021, 5),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Wrote complex SQL aggregation queries and visualized results in Power BI."
                ]
            }
        ],
        "skills_list": ["Python", "Machine Learning", "TensorFlow", "scikit-learn", "Pandas", "NumPy", "SQL", "Airflow", "Docker", "Power BI"],
        "true_skills": ["Python", "Machine Learning", "TensorFlow", "scikit-learn", "Pandas", "NumPy", "SQL", "Airflow", "Docker", "Power BI"],
        "degree": "Master of Science in Statistics",
        "education": "MS in Statistics, University of Michigan, 2018 - 2020",
        "traps": []
    })

    # DS 4: Medium (Tier 2) - two_column_pdf (Has Python, SQL, Pandas, scikit-learn, but no Deep Learning or Airflow)
    specs.append({
        "id": "ds_04_medium",
        "jd": "data_scientist",
        "tier": 2,
        "name": "Carlos Gomez",
        "roles": [
            {
                "title": "Data Scientist",
                "company": "RetailPulse",
                "dates": make_date_tuple(2022, 1, 2024, 12),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Built classification algorithms in Python with scikit-learn.",
                    "Cleaned data using Pandas and NumPy, queried MySQL databases with SQL."
                ]
            }
        ],
        "skills_list": ["Python", "Machine Learning", "scikit-learn", "Pandas", "NumPy", "SQL", "MySQL"],
        "true_skills": ["Python", "Machine Learning", "scikit-learn", "Pandas", "NumPy", "SQL", "MySQL"],
        "degree": "Bachelor of Science in Mathematics",
        "education": "BS in Mathematics, University of Texas, 2017 - 2021",
        "traps": []
    })

    # DS 5: Medium (Tier 2) - table_docx (Career gap trap)
    specs.append({
        "id": "ds_05_medium",
        "jd": "data_scientist",
        "tier": 2,
        "name": "Hannah Abbott",
        "roles": [
            {
                "title": "Data Science Specialist",
                "company": "Vivid Analytics",
                "dates": make_date_tuple(2023, 1, 2025, 1),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Trained ML models with Python, scikit-learn, and Pandas.",
                    "Wrote SQL transformations and generated Power BI reports."
                ]
            },
            # Gap from 2021-06 to 2022-12
            {
                "title": "Junior Data Analyst",
                "company": "InnoData",
                "dates": make_date_tuple(2020, 6, 2021, 6),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Manipulated datasets in Python with NumPy and SQL."
                ]
            }
        ],
        "skills_list": ["Python", "Machine Learning", "scikit-learn", "Pandas", "NumPy", "SQL", "Power BI"],
        "true_skills": ["Python", "Machine Learning", "scikit-learn", "Pandas", "NumPy", "SQL", "Power BI"],
        "degree": "Master of Science in Business Analytics",
        "education": "MS in Business Analytics, NYU, 2018 - 2020",
        "traps": ["career_gap"]
    })

    # DS 6: Medium (Tier 2) - plain_docx (Short role under one year)
    specs.append({
        "id": "ds_06_medium",
        "jd": "data_scientist",
        "tier": 2,
        "name": "Nikhil Rao",
        "roles": [
            {
                "title": "Machine Learning Contractor",
                "company": "Fintech Solutions",
                "dates": make_date_tuple(2024, 2, 2024, 9), # 8 months role
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Implemented customer churn models in Python with scikit-learn and Pandas."
                ]
            },
            {
                "title": "Data Engineer",
                "company": "StreamData",
                "dates": make_date_tuple(2021, 6, 2023, 12),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Constructed SQL data pipelines and automated jobs with Apache Airflow."
                ]
            }
        ],
        "skills_list": ["Python", "Machine Learning", "scikit-learn", "Pandas", "SQL", "Airflow"],
        "true_skills": ["Python", "Machine Learning", "scikit-learn", "Pandas", "SQL", "Airflow"],
        "degree": "Bachelor of Science in Computer Science",
        "education": "BS in Computer Science, Georgia Tech, 2017 - 2021",
        "traps": ["short_role_under_one_year"]
    })

    # DS 7: Weak (Tier 1) - single_column_pdf (Only Tableau/Excel BI reporting, no scikit-learn or Python ML)
    specs.append({
        "id": "ds_07_weak",
        "jd": "data_scientist",
        "tier": 1,
        "name": "Emily Watson",
        "roles": [
            {
                "title": "BI Dashboard Specialist",
                "company": "Global Retail Group",
                "dates": make_date_tuple(2022, 1, 2024, 6),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Created Tableau and Power BI visual dashboards.",
                    "Wrote basic SQL SELECT statements to extract sales numbers."
                ]
            }
        ],
        "skills_list": ["Tableau", "Power BI", "SQL"],
        "true_skills": ["Tableau", "Power BI", "SQL"],
        "degree": "Bachelor of Arts in Economics",
        "education": "BA in Economics, UCLA, 2018 - 2022",
        "traps": []
    })

    # DS 8: Weak (Tier 1) - two_column_pdf (Web developer with basic Python scripts)
    specs.append({
        "id": "ds_08_weak",
        "jd": "data_scientist",
        "tier": 1,
        "name": "Tom Bradley",
        "roles": [
            {
                "title": "Web Developer",
                "company": "BrightWeb Agency",
                "dates": make_date_tuple(2022, 6, 2024, 1),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Built web forms using HTML, CSS, and basic Python Flask scripts.",
                    "Stored user submissions in MySQL database."
                ]
            }
        ],
        "skills_list": ["Python", "Flask", "HTML", "CSS", "MySQL", "SQL"],
        "true_skills": ["Python", "Flask", "HTML", "CSS", "MySQL", "SQL"],
        "degree": "Associate Degree in Web Development",
        "education": "Associate Degree, DeVry, 2020 - 2022",
        "traps": []
    })

    # DS 9: Irrelevant (Tier 0) - table_docx (Graphic Designer)
    specs.append({
        "id": "ds_09_irrelevant",
        "jd": "data_scientist",
        "tier": 0,
        "name": "Jessica Taylor",
        "roles": [
            {
                "title": "Senior Creative Graphic Designer",
                "company": "Studio Prism",
                "dates": make_date_tuple(2020, 1, 2024, 12),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Designed vector illustrations, logos, and UI prototypes using Figma and Adobe Illustrator.",
                    "Created branding guidelines for corporate clients."
                ]
            }
        ],
        "skills_list": ["Adobe Illustrator", "Photoshop", "Figma", "Typography", "Visual Design"],
        "true_skills": [],
        "degree": "Bachelor of Fine Arts",
        "education": "BFA in Graphic Design, Rhode Island School of Design, 2016 - 2020",
        "traps": ["completely_irrelevant"]
    })

    # DS 10: Keyword-stuffed (Tier 1) - plain_docx (Skills dump with customer support experience)
    specs.append({
        "id": "ds_10_keyword_stuffed",
        "jd": "data_scientist",
        "tier": 1,
        "name": "Robert Vance",
        "roles": [
            {
                "title": "Helpdesk Tier 1 Support",
                "company": "OmniCall Centers",
                "dates": make_date_tuple(2021, 3, 2024, 5),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Answered telephone inquiries from retail customers and logged ticket notes in internal software.",
                    "Assisted callers with password resets."
                ]
            }
        ],
        # Stuffed with every DS skill in skills list:
        "skills_list": ["Python", "Machine Learning", "Deep Learning", "NLP", "PyTorch", "TensorFlow", "scikit-learn", "Pandas", "NumPy", "SQL", "Spark", "Airflow", "Docker", "Tableau"],
        "true_skills": ["Python", "Machine Learning", "Deep Learning", "NLP", "PyTorch", "TensorFlow", "scikit-learn", "Pandas", "NumPy", "SQL", "Spark", "Airflow", "Docker", "Tableau"],
        "degree": "High School Diploma",
        "education": "Central High School, 2017 - 2021",
        "traps": ["keyword_stuffed_skills_dump"]
    })

    # -------------------------------------------------------------
    # 3. Frontend React Engineer (10 resumes: 3 strong, 3 medium, 2 weak, 1 irrelevant, 1 keyword-stuffed)
    # -------------------------------------------------------------
    # FE 1: Strong (Tier 3) - single_column_pdf (Present date, TypeScript, React, Redux, Tailwind CSS)
    specs.append({
        "id": "fe_01_strong",
        "jd": "frontend_react",
        "tier": 3,
        "name": "Liam Gallagher",
        "roles": [
            {
                "title": "Lead Frontend React Engineer",
                "company": "Vortex Web Platforms",
                "dates": make_date_tuple(2022, 6, None, None),
                "is_present": True,
                "format": "mon_yyyy",
                "bullets": [
                    "Engineered modern responsive web applications using React, TypeScript, and Tailwind CSS.",
                    "Architected client state workflows with Redux Toolkit and managed asynchronous REST calls.",
                    "Integrated GraphQL query endpoints with Apollo Client and configured Next.js SSR.",
                    "Authored automated unit tests with Jest and React Testing Library."
                ]
            },
            {
                "title": "Frontend UI Developer",
                "company": "PixelNova Interactive",
                "dates": make_date_tuple(2020, 1, 2022, 5),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Built reusable UI component libraries using JavaScript, React, HTML5, and CSS3.",
                    "Maintained code collaboration via Git and GitHub PR reviews."
                ]
            }
        ],
        "skills_list": ["JavaScript", "TypeScript", "React", "Next.js", "Redux", "Tailwind CSS", "HTML", "CSS", "GraphQL", "REST", "Git", "Unit Testing"],
        "true_skills": ["JavaScript", "TypeScript", "React", "Next.js", "Redux", "Tailwind CSS", "HTML", "CSS", "GraphQL", "REST", "Git", "Unit Testing"],
        "degree": "Bachelor of Science in Computer Science",
        "education": "BS in Computer Science, University of California Berkeley, 2016 - 2020",
        "traps": ["present_date"]
    })

    # FE 2: Strong (Tier 3) - two_column_pdf (Overlapping jobs, React, TypeScript, Next.js, GraphQL)
    specs.append({
        "id": "fe_02_strong",
        "jd": "frontend_react",
        "tier": 3,
        "name": "Amina Al-Mansoor",
        "roles": [
            {
                "title": "Senior Frontend Developer",
                "company": "Starlight SaaS",
                "dates": make_date_tuple(2021, 6, 2025, 6),
                "is_present": False,
                "format": "slash",
                "bullets": [
                    "Architected responsive SPAs with React, TypeScript, and Tailwind CSS.",
                    "Implemented state management with Redux and integrated RESTful endpoints.",
                    "Configured SSR applications in Next.js."
                ]
            },
            {
                "title": "UI Consultant (Concurrent Contract)",
                "company": "Innovate Labs",
                "dates": make_date_tuple(2022, 1, 2023, 1), # Overlapping by 12 months
                "is_present": False,
                "format": "slash",
                "bullets": [
                    "Delivered GraphQL schema integrations and wrote unit testing suites in Jest."
                ]
            },
            {
                "title": "Web Developer",
                "company": "Echo Interactive",
                "dates": make_date_tuple(2019, 6, 2021, 5),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Constructed web pages in HTML, CSS, JavaScript, and React with Git."
                ]
            }
        ],
        "skills_list": ["JavaScript", "TypeScript", "React", "Tailwind CSS", "Redux", "Next.js", "GraphQL", "HTML", "CSS", "REST", "Git", "Unit Testing"],
        "true_skills": ["JavaScript", "TypeScript", "React", "Tailwind CSS", "Redux", "Next.js", "GraphQL", "HTML", "CSS", "REST", "Git", "Unit Testing"],
        "degree": "Bachelor of Science in Software Engineering",
        "education": "BS in Software Engineering, UT Austin, 2015 - 2019",
        "traps": ["overlapping_jobs"]
    })

    # FE 3: Strong (Tier 3) - table_docx (Node.js, Redux, React, Tailwind CSS)
    specs.append({
        "id": "fe_03_strong",
        "jd": "frontend_react",
        "tier": 3,
        "name": "Zachary Taylor",
        "roles": [
            {
                "title": "Frontend Application Engineer",
                "company": "Zephyr Cloud Systems",
                "dates": make_date_tuple(2021, 1, 2024, 12),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Developed web apps using React, TypeScript, HTML, CSS, and Tailwind CSS.",
                    "Managed client data caching with Redux Toolkit and REST APIs.",
                    "Developed backend mock services in Node.js and tracked issues using Git."
                ]
            },
            {
                "title": "Junior UI Developer",
                "company": "BrightEdge Web",
                "dates": make_date_tuple(2020, 1, 2020, 12),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Implemented responsive layouts using HTML5, CSS3, and JavaScript."
                ]
            }
        ],
        "skills_list": ["JavaScript", "TypeScript", "React", "Tailwind CSS", "Redux", "Node.js", "HTML", "CSS", "REST", "Git"],
        "true_skills": ["JavaScript", "TypeScript", "React", "Tailwind CSS", "Redux", "Node.js", "HTML", "CSS", "REST", "Git"],
        "degree": "Bachelor of Science in Computer Science",
        "education": "BS in Computer Science, University of Wisconsin, 2016 - 2020",
        "traps": []
    })

    # FE 4: Medium (Tier 2) - plain_docx (Has React, JavaScript, HTML, CSS, but missing TypeScript and Redux)
    specs.append({
        "id": "fe_04_medium",
        "jd": "frontend_react",
        "tier": 2,
        "name": "Megan Foster",
        "roles": [
            {
                "title": "React Frontend Developer",
                "company": "Prism Digital Solutions",
                "dates": make_date_tuple(2021, 6, 2024, 6),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Built customer portals using JavaScript, React, HTML, and CSS.",
                    "Consumed RESTful endpoints and maintained code in Git."
                ]
            }
        ],
        "skills_list": ["JavaScript", "React", "HTML", "CSS", "REST", "Git"],
        "true_skills": ["JavaScript", "React", "HTML", "CSS", "REST", "Git"],
        "degree": "Bachelor of Arts in Media Arts & Science",
        "education": "BA in Media Arts, Indiana University, 2017 - 2021",
        "traps": []
    })

    # FE 5: Medium (Tier 2) - single_column_pdf (Career gap trap)
    specs.append({
        "id": "fe_05_medium",
        "jd": "frontend_react",
        "tier": 2,
        "name": "Oliver Quinn",
        "roles": [
            {
                "title": "Frontend Engineer",
                "company": "OmniFlow Systems",
                "dates": make_date_tuple(2023, 2, 2025, 2),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Developed Single Page Applications with React, TypeScript, HTML, and Tailwind CSS.",
                    "Connected interfaces with backend REST APIs."
                ]
            },
            # Gap from 2021-06 to 2023-01
            {
                "title": "Junior Web Designer",
                "company": "ClearView Sites",
                "dates": make_date_tuple(2020, 6, 2021, 6),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Built landing pages using HTML, CSS, and basic JavaScript."
                ]
            }
        ],
        "skills_list": ["JavaScript", "TypeScript", "React", "Tailwind CSS", "HTML", "CSS", "REST"],
        "true_skills": ["JavaScript", "TypeScript", "React", "Tailwind CSS", "HTML", "CSS", "REST"],
        "degree": "Bachelor of Science in Information Systems",
        "education": "BS in Information Systems, Arizona State University, 2016 - 2020",
        "traps": ["career_gap"]
    })

    # FE 6: Medium (Tier 2) - two_column_pdf (Short role under one year trap)
    specs.append({
        "id": "fe_06_medium",
        "jd": "frontend_react",
        "tier": 2,
        "name": "Danielle Morgan",
        "roles": [
            {
                "title": "Frontend UI Contractor",
                "company": "RapidLaunch Tech",
                "dates": make_date_tuple(2024, 1, 2024, 8), # 7 months
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Engineered modular React and TypeScript components styled with Tailwind CSS."
                ]
            },
            {
                "title": "Web Specialist",
                "company": "CoreMedia",
                "dates": make_date_tuple(2021, 1, 2023, 10),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Developed web pages in JavaScript, HTML5, CSS3, and Git."
                ]
            }
        ],
        "skills_list": ["JavaScript", "TypeScript", "React", "Tailwind CSS", "HTML", "CSS", "Git"],
        "true_skills": ["JavaScript", "TypeScript", "React", "Tailwind CSS", "HTML", "CSS", "Git"],
        "degree": "Bachelor of Science in Computer Science",
        "education": "BS in Computer Science, University of Oregon, 2017 - 2021",
        "traps": ["short_role_under_one_year"]
    })

    # FE 7: Weak (Tier 1) - table_docx (Angular and Vue only, no React)
    specs.append({
        "id": "fe_07_weak",
        "jd": "frontend_react",
        "tier": 1,
        "name": "Kelsey Stewart",
        "roles": [
            {
                "title": "Frontend Developer",
                "company": "Horizon Apps",
                "dates": make_date_tuple(2022, 1, 2024, 6),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Constructed web components in Angular and Vue.js.",
                    "Styled views using CSS and HTML, integrated REST APIs."
                ]
            }
        ],
        "skills_list": ["JavaScript", "Angular", "Vue", "HTML", "CSS", "REST"],
        "true_skills": ["JavaScript", "Angular", "Vue", "HTML", "CSS", "REST"],
        "degree": "Bachelor of Science in Software Engineering",
        "education": "BS in Software Engineering, Iowa State, 2018 - 2022",
        "traps": []
    })

    # FE 8: Weak (Tier 1) - plain_docx (Junior with 6 months HTML/CSS)
    specs.append({
        "id": "fe_08_weak",
        "jd": "frontend_react",
        "tier": 1,
        "name": "Brandon Cole",
        "roles": [
            {
                "title": "Intern Web Assistant",
                "company": "StarterWeb Studio",
                "dates": make_date_tuple(2024, 6, 2024, 12),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Updated static HTML and CSS stylesheets."
                ]
            }
        ],
        "skills_list": ["HTML", "CSS"],
        "true_skills": ["HTML", "CSS"],
        "degree": "High School Diploma",
        "education": "Westlake High School, 2020 - 2024",
        "traps": ["short_experience"]
    })

    # FE 9: Irrelevant (Tier 0) - single_column_pdf (Accountant)
    specs.append({
        "id": "fe_09_irrelevant",
        "jd": "frontend_react",
        "tier": 0,
        "name": "Patricia Morales",
        "roles": [
            {
                "title": "Certified Public Accountant",
                "company": "Sterling & Associates CPA",
                "dates": make_date_tuple(2019, 1, 2024, 6),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Prepared corporate income tax filings and conducted quarterly financial audits.",
                    "Reconciled ledger balances and verified QuickBooks payroll sheets."
                ]
            }
        ],
        "skills_list": ["Financial Auditing", "QuickBooks", "Tax Compliance", "Payroll Accounting", "GAAP"],
        "true_skills": [],
        "degree": "Bachelor of Business Administration in Accounting",
        "education": "BBA in Accounting, Texas A&M University, 2015 - 2019",
        "traps": ["completely_irrelevant"]
    })

    # FE 10: Keyword-stuffed (Tier 1) - two_column_pdf (Skills dump with warehouse associate experience)
    specs.append({
        "id": "fe_10_keyword_stuffed",
        "jd": "frontend_react",
        "tier": 1,
        "name": "Gary Higgins",
        "roles": [
            {
                "title": "Warehouse Logistics Associate",
                "company": "Prime Logistics Hub",
                "dates": make_date_tuple(2021, 1, 2024, 1),
                "is_present": False,
                "format": "mon_yyyy",
                "bullets": [
                    "Unloaded delivery trucks and scanned inventory pallets into inventory tracking scanners.",
                    "Ensured warehouse aisle safety compliance."
                ]
            }
        ],
        # Stuffed with every Frontend React skill in skills list:
        "skills_list": ["JavaScript", "TypeScript", "React", "Next.js", "Redux", "Tailwind CSS", "HTML", "CSS", "GraphQL", "REST", "Git", "Unit Testing", "Node.js"],
        "true_skills": ["JavaScript", "TypeScript", "React", "Next.js", "Redux", "Tailwind CSS", "HTML", "CSS", "GraphQL", "REST", "Git", "Unit Testing", "Node.js"],
        "degree": "High School Diploma",
        "education": "Oakridge High School, 2016 - 2020",
        "traps": ["keyword_stuffed_skills_dump"]
    })

    return specs


# =====================================================================
# Document Layout Renderers
# =====================================================================

def render_single_column_pdf(spec: Dict[str, Any], filepath: Path):
    """Render single-column PDF with PyMuPDF."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842) # A4
    margin = 50
    w = 595 - 2 * margin
    
    # Construct structured text
    lines = []
    lines.append(spec["name"])
    lines.append(f"{spec['name'].lower().replace(' ', '.')}@example.com | (555) 234-5678 | San Francisco, CA")
    lines.append("")
    
    lines.append("PROFESSIONAL SUMMARY")
    lines.append(f"Experienced professional specializing in {spec['jd'].replace('_', ' ')} solutions with demonstrated history of delivery.")
    lines.append("")
    
    lines.append("TECHNICAL SKILLS")
    lines.append(", ".join(spec["skills_list"]))
    lines.append("")
    
    lines.append("WORK EXPERIENCE")
    for r in spec["roles"]:
        date_str = format_date_str(r["dates"][0], r["dates"][1], r.get("is_present", False), r.get("format", "mon_yyyy"))
        lines.append(f"{r['title']} - {r['company']}")
        lines.append(date_str)
        for b in r["bullets"]:
            lines.append(f"- {b}")
        lines.append("")
        
    lines.append("EDUCATION")
    lines.append(spec["education"])

    full_text = "\n".join(lines)
    rect = pymupdf.Rect(margin, margin, margin + w, 842 - margin)
    page.insert_textbox(rect, full_text, fontsize=9.5, fontname="helv", lineheight=1.2)
    doc.save(str(filepath))
    doc.close()


def render_two_column_pdf(spec: Dict[str, Any], filepath: Path):
    """Render two-column PDF with PyMuPDF."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    margin = 40
    col_gap = 20
    col1_w = 170
    col2_w = 595 - 2 * margin - col1_w - col_gap
    
    # Header across top
    header_rect = pymupdf.Rect(margin, margin, 595 - margin, margin + 45)
    header_text = f"{spec['name']}\n{spec['name'].lower().replace(' ', '.')}@example.com | (555) 345-6789"
    page.insert_textbox(header_rect, header_text, fontsize=12, fontname="helv")
    
    # Left column: Skills & Education
    left_lines = [
        "TECHNICAL SKILLS",
        "\n".join(f"- {s}" for s in spec["skills_list"]),
        "",
        "EDUCATION",
        spec["education"]
    ]
    left_rect = pymupdf.Rect(margin, margin + 55, margin + col1_w, 842 - margin)
    page.insert_textbox(left_rect, "\n".join(left_lines), fontsize=9, fontname="helv", lineheight=1.2)
    
    # Right column: Experience & Summary
    right_lines = [
        "PROFESSIONAL SUMMARY",
        f"Qualified {spec['jd'].replace('_', ' ')} practitioner with industry background.",
        "",
        "WORK EXPERIENCE"
    ]
    for r in spec["roles"]:
        date_str = format_date_str(r["dates"][0], r["dates"][1], r.get("is_present", False), r.get("format", "mon_yyyy"))
        right_lines.append(f"{r['title']}")
        right_lines.append(f"{r['company']} | {date_str}")
        for b in r["bullets"]:
            right_lines.append(f"- {b}")
        right_lines.append("")

    right_rect = pymupdf.Rect(margin + col1_w + col_gap, margin + 55, 595 - margin, 842 - margin)
    page.insert_textbox(right_rect, "\n".join(right_lines), fontsize=9, fontname="helv", lineheight=1.2)
    doc.save(str(filepath))
    doc.close()


def render_table_docx(spec: Dict[str, Any], filepath: Path):
    """Render table-based DOCX with python-docx."""
    doc = docx.Document()
    
    # Header block
    p = doc.add_paragraph()
    run = p.add_run(spec["name"])
    run.font.size = Pt(18)
    run.font.bold = True
    p2 = doc.add_paragraph(f"{spec['name'].lower().replace(' ', '.')}@example.com | (555) 456-7890 | Austin, TX")
    
    doc.add_heading("Professional Summary", level=2)
    doc.add_paragraph(f"Dedicated {spec['jd'].replace('_', ' ')} with extensive background.")
    
    doc.add_heading("Technical Skills", level=2)
    table_skills = doc.add_table(rows=1, cols=2)
    hdr_cells = table_skills.rows[0].cells
    hdr_cells[0].text = "Category"
    hdr_cells[1].text = "Technologies"
    row = table_skills.add_row().cells
    row[0].text = "Core Competencies"
    row[1].text = ", ".join(spec["skills_list"])
    
    doc.add_heading("Work Experience", level=2)
    table_exp = doc.add_table(rows=0, cols=2)
    for r in spec["roles"]:
        date_str = format_date_str(r["dates"][0], r["dates"][1], r.get("is_present", False), r.get("format", "mon_yyyy"))
        row = table_exp.add_row().cells
        row[0].text = date_str
        bullet_text = f"{r['title']} at {r['company']}\n" + "\n".join(f"- {b}" for b in r["bullets"])
        row[1].text = bullet_text
        
    doc.add_heading("Education", level=2)
    doc.add_paragraph(spec["education"])
    
    doc.save(str(filepath))


def render_plain_docx(spec: Dict[str, Any], filepath: Path):
    """Render plain DOCX with python-docx."""
    doc = docx.Document()
    
    # Header
    p = doc.add_paragraph()
    r = p.add_run(spec["name"])
    r.font.size = Pt(16)
    r.font.bold = True
    doc.add_paragraph(f"{spec['name'].lower().replace(' ', '.')}@example.com | (555) 567-8901 | New York, NY")
    
    doc.add_heading("Professional Summary", level=2)
    doc.add_paragraph(f"Professional profile for {spec['name']} focusing on {spec['jd'].replace('_', ' ')}.")
    
    doc.add_heading("Key Skills", level=2)
    doc.add_paragraph(", ".join(spec["skills_list"]))
    
    doc.add_heading("Work Experience", level=2)
    for r in spec["roles"]:
        date_str = format_date_str(r["dates"][0], r["dates"][1], r.get("is_present", False), r.get("format", "mon_yyyy"))
        p = doc.add_paragraph()
        run = p.add_run(f"{r['title']} - {r['company']}")
        run.bold = True
        doc.add_paragraph(date_str)
        for b in r["bullets"]:
            doc.add_paragraph(f"- {b}")
            
    doc.add_heading("Education", level=2)
    doc.add_paragraph(spec["education"])
    
    doc.save(str(filepath))


def main():
    base_dir = Path(__file__).resolve().parent.parent
    resumes_dir = base_dir / "eval" / "resumes"
    gold_path = base_dir / "eval" / "gold.json"
    resumes_dir.mkdir(parents=True, exist_ok=True)
    
    specs = get_resume_specs()
    gold_data = {}

    print(f"Generating {len(specs)} synthetic resumes...")

    for idx, spec in enumerate(specs):
        layout = LAYOUTS[idx % len(LAYOUTS)]
        ext = ".pdf" if "pdf" in layout else ".docx"
        filename = f"{spec['id']}{ext}"
        filepath = resumes_dir / filename
        
        # Calculate true total years exactly using the date tuples
        date_ranges = [r["dates"] for r in spec["roles"]]
        true_total_years = calculate_total_years(date_ranges)
        
        # Render document
        if layout == "single_column_pdf":
            render_single_column_pdf(spec, filepath)
        elif layout == "two_column_pdf":
            render_two_column_pdf(spec, filepath)
        elif layout == "table_docx":
            render_table_docx(spec, filepath)
        elif layout == "plain_docx":
            render_plain_docx(spec, filepath)

        gold_data[filename] = {
            "id": spec["id"],
            "jd": spec["jd"],
            "name": spec["name"],
            "tier": spec["tier"],
            "true_skills": spec["true_skills"],
            "true_total_years": true_total_years,
            "layout": layout,
            "degree": spec["degree"],
            "traps": spec["traps"]
        }
        print(f"  [{idx+1:02d}/30] Generated {filename:28} | Layout: {layout:18} | Tier: {spec['tier']} | Years: {true_total_years:.1f}")

    with open(gold_path, "w", encoding="utf-8") as f:
        json.dump(gold_data, f, indent=2)

    print(f"\nSUCCESS: Generated 30 resumes in '{resumes_dir}' and annotated '{gold_path}'.")

if __name__ == "__main__":
    main()
