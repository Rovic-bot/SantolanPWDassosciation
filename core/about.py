"""Owner-supplied About copy and safe plain-text section formatting."""
import re


ABOUT_TITLE = 'About the Association'
ABOUT_BODY = """## Background

The Barangay Santolan PWD Association supports persons with disabilities in the community through membership services, rights advocacy, community participation, and information about available programs and assistance.

## Our mission

To support the well-being, rights, independence, and participation of persons with disabilities in Barangay Santolan through an inclusive and supportive community.

## Association’s Purposes

- To promote the well-being and integration of PWDs into society by advocating for their rights, providing support services and fostering an inclusive environment, positive attitudes and reducing stigma.
- To provide services to help the PWDs maximize their functional abilities and independence.
- To raise public awareness about disability issues, advocating policy changes and promoting the rights of PWDs.

## Association’s Objectives

- Enhancing the quality of life for PWDs.
- Developing the skills and capabilities of PWDs to participate in social and economic activities.
- Monitoring and advocating for the implementation of laws and policies that protect the rights of PWDs.
- Organizing PWDs into self-help groups and fostering mutual support and peer counselling.

## Association membership and services

Association membership connects PWDs with the Association’s support, community activities, and member services. Membership registration includes onsite requirements review and an authorized membership decision.

The Association provides membership guidance, official updates, program information, and assistance information with referral support. Program applications and referral requests require verified Association membership. Each program has its own requirements, and submitting an application or referral request does not guarantee assistance.

## PDAO’s PWD ID processing

Government PWD registration and PWD ID processing are handled through PDAO and are separate from Association membership. This portal lets applicants submit a PDAO form for private staff review, printing and preparation for forwarding, with in-person verification handled through PDAO. Preparing a form does not issue a PWD ID or approve Association membership.

## Public information for non-members

Non-members can browse Association information, Announcements, Events, Programs, authorized Program Results, membership and PWD ID guidance, and Resources & Help without a member account. Resources & Help → Where Can I Get Help? provides information about available services.
"""


def about_blocks(body):
    """Recognize headings and bullet groups; templates still escape all text."""
    blocks = []
    for paragraph in re.split(r'\n\s*\n', body.replace('\r\n', '\n').strip()):
        lines = [line.strip() for line in paragraph.splitlines()]
        if not lines:
            continue
        if len(lines) == 1 and lines[0].startswith('## '):
            blocks.append({'kind': 'heading', 'text': lines[0][3:]})
        elif all(line.startswith('- ') for line in lines):
            blocks.append({'kind': 'list', 'items': [line[2:] for line in lines]})
        else:
            blocks.append({'kind': 'paragraph', 'text': paragraph})
    return blocks
