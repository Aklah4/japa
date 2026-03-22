from flask import Flask, render_template, request, session, redirect, url_for

app = Flask(__name__)
app.secret_key = 'japa-mvp-2026'


# ── CRS SCORE CALCULATOR ─────────────────────────────────────────────────────

def calc_age_points(age):
    table = {
        18: 99, 19: 105,
        30: 105, 31: 99, 32: 94, 33: 88, 34: 83,
        35: 77,  36: 72, 37: 66, 38: 61, 39: 55,
        40: 50,  41: 39, 42: 28, 43: 17, 44: 6,
    }
    if 20 <= age <= 29:
        return 110
    return table.get(age, 0)


def calc_education_points(edu):
    return {
        'doctoral':   150,
        'masters':    135,
        'bachelors':  120,
        'diploma_2':   98,
        'diploma_1':   90,
        'secondary':   30,
        'none':         0,
    }.get(edu, 0)


def calc_language_points(clb):
    per_skill = {10: 34, 9: 31, 8: 23, 7: 17, 6: 9, 5: 6}
    pts = per_skill.get(clb, 34 if clb > 10 else 0)
    return pts * 4   # 4 skills


def calc_ca_exp_points(years):
    return {0: 0, 1: 40, 2: 53, 3: 64, 4: 72}.get(years, 80)


def calc_transferability(edu_pts, lang_per_skill, ca_exp, foreign_exp):
    pts = 0
    # Education + language
    if edu_pts >= 120 and lang_per_skill >= 17:
        pts += 25
    elif edu_pts >= 90 and lang_per_skill >= 17:
        pts += 13
    # Foreign experience + language
    if foreign_exp >= 3 and lang_per_skill >= 17:
        pts += 25
    elif foreign_exp >= 1 and lang_per_skill >= 17:
        pts += 13
    # Foreign experience + Canadian experience
    if foreign_exp >= 3 and ca_exp >= 2:
        pts += 25
    elif foreign_exp >= 1 and ca_exp >= 1:
        pts += 13
    return min(pts, 100)


def calculate_crs(data):
    age        = int(data['age'])
    clb        = int(data['clb'])
    ca_exp     = int(data['ca_experience'])
    foreign    = int(data['foreign_experience'])
    edu        = data['education']

    age_pts  = calc_age_points(age)
    edu_pts  = calc_education_points(edu)
    lang_pts = calc_language_points(clb)
    ca_pts   = calc_ca_exp_points(ca_exp)

    per_skill = {10: 34, 9: 31, 8: 23, 7: 17, 6: 9, 5: 6}.get(clb, 34 if clb > 10 else 0)
    transfer_pts = calc_transferability(edu_pts, per_skill, ca_exp, foreign)

    total = age_pts + edu_pts + lang_pts + ca_pts + transfer_pts

    return {
        'total':        total,
        'age':          age_pts,
        'education':    edu_pts,
        'language':     lang_pts,
        'ca_experience': ca_pts,
        'transferability': transfer_pts,
    }


# ── RECOMMENDATION ENGINE ────────────────────────────────────────────────────

CAREER_NOCS = {
    'tech':      ['Software Engineers (NOC 21230)', 'Data Scientists (NOC 21211)', 'IT Project Managers (NOC 20012)'],
    'health':    ['Registered Nurses (NOC 31301)', 'General Practitioners (NOC 31102)', 'Physiotherapists (NOC 31202)'],
    'trades':    ['Electricians (NOC 72200)', 'Plumbers (NOC 72300)', 'Welders (NOC 72106)'],
    'business':  ['Financial Analysts (NOC 11101)', 'Accountants (NOC 11100)', 'HR Managers (NOC 10011)'],
    'education': ['College Instructors (NOC 41210)', 'Secondary Teachers (NOC 41221)', 'Early Childhood Educators (NOC 42202)'],
    'other':     ['Federal Skilled Worker pathway', 'Check the NOC list for your occupation'],
}

CAREER_PNP = {
    'tech':      'BC PNP Tech Pilot, Ontario Tech Draw, Alberta Advantage Tech Stream',
    'health':    'Alberta Healthcare stream, BC Health Authority, Saskatchewan Healthcare',
    'trades':    'Saskatchewan Trades & Occupations, Alberta Opportunity Stream',
    'business':  'Ontario Business Stream, Nova Scotia Labour Market Priorities',
    'education': 'Manitoba Education Stream, New Brunswick Skilled Workers',
    'other':     "Research your province's PNP streams at canada.ca/pnp",
}


def get_recommendation(score, clb, ca_exp, education, career):
    clb    = int(clb)
    ca_exp = int(ca_exp)
    fsw_eligible = clb >= 7 and education not in ('none', 'secondary')

    if score >= 470:
        status   = 'Strong'
        colour   = '#4a7c3f'
        message  = 'Your profile is highly competitive. You are within range of recent Express Entry draws.'
        pathways = ['Express Entry – Federal Skilled Worker (FSW)', 'Canadian Experience Class (CEC)']
    elif score >= 440:
        status   = 'Good'
        colour   = '#a07848'
        message  = 'You qualify for Express Entry. A Provincial Nominee Program (PNP) nomination adds +600 points and fast-tracks your application.'
        pathways = ['Express Entry – FSW', 'Provincial Nominee Program (PNP) – Enhanced', 'Canadian Experience Class']
    elif score >= 400:
        status   = 'Moderate'
        colour   = '#b07030'
        message  = 'Consider a Provincial Nominee Program stream or improve your language score (CLB 9+) to become more competitive.'
        pathways = ['Provincial Nominee Program (PNP)', 'Improve language score', 'Gain Canadian work experience']
    else:
        status   = 'Developing'
        colour   = '#9c4040'
        message  = 'Focus on boosting your score. Priority areas: language proficiency, Canadian experience, or higher credentials.'
        pathways = ['Improve language (aim CLB 9+)', 'Apply for a Canadian work/study permit', 'Obtain a skills assessment (ECA via WES)']

    return {
        'status':           status,
        'colour':           colour,
        'message':          message,
        'pathways':         pathways,
        'career_nocs':      CAREER_NOCS.get(career, CAREER_NOCS['other']),
        'career_pnp':       CAREER_PNP.get(career, CAREER_PNP['other']),
        'fsw_eligible':     fsw_eligible,
    }


def get_timeline(score):
    if score >= 470:
        return {'range': '6 – 12 months',  'note': 'From ITA to PR landing, typical Express Entry timeline'}
    elif score >= 440:
        return {'range': '12 – 18 months', 'note': 'Including PNP processing if applicable'}
    elif score >= 400:
        return {'range': '18 – 24 months', 'note': 'After improving score or receiving PNP nomination'}
    else:
        return {'range': '24+ months',     'note': 'Timeline begins after score improvement phase'}


def get_cost_estimate():
    return [
        {'item': 'IELTS / CELPIP Language Test',    'low': 280,   'high': 340},
        {'item': 'WES Educational Credential (ECA)', 'low': 239,   'high': 300},
        {'item': 'Medical Examination (per person)', 'low': 450,   'high': 700},
        {'item': 'Biometrics (per person)',           'low': 85,    'high': 85},
        {'item': 'Government Application Fee (PR)',   'low': 1365,  'high': 1365},
        {'item': 'Translation & Other Documents',    'low': 200,   'high': 600},
    ]


def get_document_checklist(education, career):
    docs = [
        {'name': 'Valid Passport',                              'required': True,  'note': 'Must cover full application period'},
        {'name': 'Language Test Results (IELTS/CELPIP/TEF)',    'required': True,  'note': 'Must be less than 2 years old'},
        {'name': 'Educational Credential Assessment (WES)',     'required': True,  'note': 'For all non-Canadian degrees'},
        {'name': 'Employment Reference Letters',                'required': True,  'note': 'On company letterhead, signed by HR'},
        {'name': 'Police Clearance Certificates',               'required': True,  'note': 'All countries lived in 6+ months'},
        {'name': 'Medical Examination',                         'required': True,  'note': 'By IRCC-approved physician only'},
        {'name': 'Proof of Funds (Bank Statements)',            'required': True,  'note': '3–6 months of statements'},
        {'name': 'Birth Certificate',                           'required': True,  'note': 'With certified English/French translation'},
        {'name': "National ID / Driver's License",              'required': False, 'note': 'Supporting identity document'},
        {'name': 'Marriage Certificate',                        'required': False, 'note': 'Required if married'},
        {'name': 'Payslips / Tax Returns (3 years)',            'required': False, 'note': 'Strongly recommended'},
        {'name': 'Job Offer Letter (if applicable)',            'required': False, 'note': '+200 pts if LMIA-exempt or LMIA approved'},
    ]
    return docs


# ── ROUTES ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('japa.html')


@app.route('/input', methods=['GET', 'POST'])
def input_form():
    if request.method == 'POST':
        session['user_data'] = {
            'name':               request.form.get('name', ''),
            'age':                request.form.get('age'),
            'education':          request.form.get('education'),
            'clb':                request.form.get('clb'),
            'ca_experience':      request.form.get('ca_experience'),
            'foreign_experience': request.form.get('foreign_experience'),
            'marital':            request.form.get('marital'),
            'career':             request.form.get('career'),
        }
        return redirect(url_for('results'))
    return render_template('input.html')


@app.route('/results')
def results():
    data = session.get('user_data')
    if not data:
        return redirect(url_for('input_form'))

    # Guard against missing or non-numeric session values
    required_fields = ('age', 'clb', 'ca_experience', 'foreign_experience', 'education', 'career')
    if any(not data.get(f) for f in required_fields):
        return redirect(url_for('input_form'))

    try:
        crs = calculate_crs(data)
    except (ValueError, TypeError):
        return redirect(url_for('input_form'))

    rec      = get_recommendation(crs['total'], data['clb'], data['ca_experience'], data['education'], data['career'])
    timeline = get_timeline(crs['total'])
    costs    = get_cost_estimate()
    docs     = get_document_checklist(data['education'], data['career'])

    total_low  = sum(c['low']  for c in costs)
    total_high = sum(c['high'] for c in costs)

    return render_template('results.html',
        user=data,
        crs=crs,
        recommendation=rec,
        timeline=timeline,
        costs=costs,
        total_low=total_low,
        total_high=total_high,
        documents=docs,
    )


if __name__ == '__main__':
    app.run(debug=True)
