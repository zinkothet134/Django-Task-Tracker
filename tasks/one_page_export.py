"""Create a compact editable .docx Activity Summary similar to the supplied sample."""
from io import BytesIO

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt


def build_one_page_document(name, position, month_label, completed_heading,
                            ongoing_heading, completed, ongoing):
    document = Document()
    section = document.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)  # A4
    section.left_margin = section.right_margin = Cm(1.5)
    section.top_margin = Cm(1.35)
    section.bottom_margin = Cm(1.35)

    normal = document.styles['Normal']
    normal.font.name = 'Arial'
    normal.font.size = Pt(10)
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.line_spacing = 1.08

    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(18)
    run = title.add_run('Activity Summary')
    run.bold = True
    run.font.size = Pt(15)

    for label, value in [('Name', name), ('Position', position), ('Month', month_label)]:
        line = document.add_paragraph()
        line.paragraph_format.space_after = Pt(4)
        line.add_run(f'{label}\t= ')
        bold = line.add_run(value)
        bold.bold = True
        line.paragraph_format.tab_stops.add_tab_stop(Cm(2.7))

    def section_items(heading, items):
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_before = Pt(17)
        paragraph.paragraph_format.space_after = Pt(6)
        paragraph.paragraph_format.keep_with_next = True
        run = paragraph.add_run(heading)
        run.bold = True
        run.underline = True
        run.font.size = Pt(11)

        if not items:
            items = ['No entries for this section; review and update before submitting.']
        for item in items:
            p = document.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.65)
            p.paragraph_format.first_line_indent = Cm(-0.32)
            p.paragraph_format.space_after = Pt(3)
            p.add_run('-  ' + item)

    section_items(completed_heading, completed)
    section_items(ongoing_heading, ongoing)
    output = BytesIO()
    document.save(output)
    return output.getvalue()
