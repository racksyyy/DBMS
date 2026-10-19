"""PLACEHOLDER corpus: fictional college catalog and policy text.

Replace the text with your real college documents when you have them.
Structure stays the same:
  DOCS      -> documents, each with chunks, each chunk lists the entities it mentions
  RELATIONS -> graph edges, each pointing at the chunk that supports it
"""

# Entities as (name, type) so relations can't contain typos
CSE101 = ("CSE101 Programming Fundamentals", "COURSE")
CSE201 = ("CSE201 Data Structures", "COURSE")
CSE301 = ("CSE301 Database Systems", "COURSE")
CSE305 = ("CSE305 Machine Learning", "COURSE")
MAT201 = ("MAT201 Probability and Statistics", "COURSE")
DEPT_CS = ("Department of Computer Science", "DEPARTMENT")
DEPT_MATH = ("Department of Mathematics", "DEPARTMENT")
BTECH_CSE = ("B.Tech CSE", "PROGRAM")
DS_MINOR = ("Data Science Minor", "PROGRAM")
ATTENDANCE = ("Attendance Policy", "POLICY")
CONDONATION = ("Attendance Condonation Rule", "RULE")
REGISTRATION = ("Course Registration Policy", "POLICY")
WAIVER = ("Prerequisite Waiver", "RULE")
GRADING = ("Grading Policy", "POLICY")
PROBATION = ("Academic Probation", "RULE")
SUPPLEMENTARY = ("Supplementary Exam Rule", "RULE")

DOCS = [
    {
        "title": "Course Catalog - CSE",
        "doc_type": "COURSE",
        "source": "placeholder/course_catalog.txt",
        "chunks": [
            {"text": "CSE201 Data Structures covers arrays, linked lists, trees and graphs. "
                     "Prerequisite: CSE101 Programming Fundamentals.",
             "entities": [CSE201, CSE101]},
            {"text": "CSE301 Database Systems introduces relational modelling, SQL and "
                     "transaction management. Prerequisite: CSE201 Data Structures.",
             "entities": [CSE301, CSE201]},
            {"text": "CSE305 Machine Learning requires CSE201 Data Structures and MAT201 "
                     "Probability and Statistics. It is offered by the Department of Computer Science.",
             "entities": [CSE305, CSE201, MAT201, DEPT_CS]},
            {"text": "MAT201 Probability and Statistics is offered by the Department of Mathematics "
                     "and is a core course for the B.Tech CSE program.",
             "entities": [MAT201, DEPT_MATH, BTECH_CSE]},
        ],
    },
    {
        "title": "Academic Regulations",
        "doc_type": "POLICY",
        "source": "placeholder/academic_regulations.txt",
        "chunks": [
            {"text": "Minimum attendance: students must maintain at least 75% attendance in every "
                     "course to be eligible for end-semester examinations. This applies to all "
                     "B.Tech programs.",
             "entities": [ATTENDANCE, BTECH_CSE]},
            {"text": "Condonation of shortage: students with attendance between 65% and 75% may "
                     "apply for condonation with a valid medical certificate, subject to a fee. "
                     "Below 65%, no condonation is permitted.",
             "entities": [ATTENDANCE, CONDONATION]},
            {"text": "Course registration: a student may register for a course only after "
                     "completing its prerequisites. Exceptions require written approval from the "
                     "Head of Department.",
             "entities": [REGISTRATION, WAIVER]},
            {"text": "Grading: a minimum CGPA of 5.0 is required to remain in good academic "
                     "standing. Students below 5.0 for two consecutive semesters are placed on "
                     "academic probation.",
             "entities": [GRADING, PROBATION]},
        ],
    },
    {
        "title": "Examination Rules",
        "doc_type": "POLICY",
        "source": "placeholder/exam_rules.txt",
        "chunks": [
            {"text": "Students detained because of attendance shortage cannot appear for "
                     "end-semester exams, but may reappear in the supplementary exam after "
                     "re-registering for the course.",
             "entities": [ATTENDANCE, SUPPLEMENTARY]},
            {"text": "Supplementary examinations are held once a year. A student may attempt a "
                     "course in the supplementary exam at most twice.",
             "entities": [SUPPLEMENTARY]},
        ],
    },
    {
        "title": "Minor Program Guidelines",
        "doc_type": "PROGRAM",
        "source": "placeholder/minor_guidelines.txt",
        "chunks": [
            {"text": "Students may pursue a Data Science Minor alongside the B.Tech CSE program. "
                     "The minor requires 18 credits, including CSE305 Machine Learning.",
             "entities": [DS_MINOR, BTECH_CSE, CSE305]},
            {"text": "Minor courses must be completed by the end of the 8th semester and do not "
                     "count toward the major CGPA.",
             "entities": [DS_MINOR, GRADING]},
        ],
    },
]

# (source entity, relation, target entity, supporting document title, chunk index in that document)
RELATIONS = [
    (CSE201, "REQUIRES", CSE101, "Course Catalog - CSE", 0),
    (CSE301, "REQUIRES", CSE201, "Course Catalog - CSE", 1),
    (CSE305, "REQUIRES", CSE201, "Course Catalog - CSE", 2),
    (CSE305, "REQUIRES", MAT201, "Course Catalog - CSE", 2),
    (CSE305, "OFFERED_BY", DEPT_CS, "Course Catalog - CSE", 2),
    (MAT201, "OFFERED_BY", DEPT_MATH, "Course Catalog - CSE", 3),
    (MAT201, "CORE_FOR", BTECH_CSE, "Course Catalog - CSE", 3),
    (ATTENDANCE, "APPLIES_TO", BTECH_CSE, "Academic Regulations", 0),
    (CONDONATION, "EXCEPTION_TO", ATTENDANCE, "Academic Regulations", 1),
    (WAIVER, "EXCEPTION_TO", REGISTRATION, "Academic Regulations", 2),
    (PROBATION, "ENFORCED_BY", GRADING, "Academic Regulations", 3),
    (SUPPLEMENTARY, "FOLLOWS_FROM", ATTENDANCE, "Examination Rules", 0),
    (DS_MINOR, "INCLUDES", CSE305, "Minor Program Guidelines", 0),
    (DS_MINOR, "OFFERED_WITH", BTECH_CSE, "Minor Program Guidelines", 0),
    (DS_MINOR, "EXCLUDED_FROM", GRADING, "Minor Program Guidelines", 1),
    # Cross-document links: courses with prerequisites fall under the registration policy
    (CSE201, "GOVERNED_BY", REGISTRATION, "Academic Regulations", 2),
    (CSE301, "GOVERNED_BY", REGISTRATION, "Academic Regulations", 2),
    (CSE305, "GOVERNED_BY", REGISTRATION, "Academic Regulations", 2),
]