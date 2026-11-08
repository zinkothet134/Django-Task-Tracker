"""Monthly work logs and Excel export for TaskFlow.
Install via apply_timesheet.py, then run makemigrations and migrate.
"""
import calendar
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO

import xlsxwriter
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from .models import TimesheetEntry, TimesheetPreference


def _month_range(raw):
    if not raw:
        raw = timezone.localdate().strftime('%Y-%m')
    try:
        first = date.fromisoformat(f'{raw}-01')
        if not (2000 <= first.year <= 2100):
            raise ValueError('Year out of bounds')
    except (ValueError, TypeError):
        first = timezone.localdate().replace(day=1)
    count = calendar.monthrange(first.year, first.month)[1]
    return first, first + timedelta(days=count - 1), count


def _month_rows(user, first, count):
    last = first + timedelta(days=count - 1)
    by_date = {item.date: item for item in TimesheetEntry.objects.filter(user=user, date__range=(first, last))}
    rows = []
    for offset in range(count):
        current = first + timedelta(days=offset)
        entry = by_date.get(current)
        rows.append({
            'date': current,
            'key': current.strftime('%Y%m%d'),
            'weekend': current.weekday() >= 5,
            'day_type': entry.day_type if entry else '',
            'hours': str(entry.hours).rstrip('0').rstrip('.') if entry and entry.day_type == 'WORK' else '',
            'activities': entry.activities if entry else '',
        })
    return rows


@login_required
def monthly_timesheet(request):
    """Save a month with friendly errors and without discarding user/AI text.

    Timesheet validation UI: the browser validates first; the server remains
    authoritative and rerenders invalid POST values without deleting entries.
    """
    first, last, count = _month_range(
        request.POST.get('month') if request.method == 'POST' else request.GET.get('month')
    )
    preference, _ = TimesheetPreference.objects.get_or_create(user=request.user)
    default_name = request.user.get_full_name() or request.user.username
    context = {
        'month': first.strftime('%Y-%m'),
        'month_title': first.strftime('%B %Y'),
        'rows': _month_rows(request.user, first, count),
        'preference': preference,
        'default_name': default_name,
        'form_organization': preference.organization,
        'form_display_name': preference.display_name or default_name,
        'form_position': preference.position,
        'saved': request.method == 'GET' and request.GET.get('saved') == '1',
    }

    if request.method == 'POST':
        organization = (request.POST.get('organization') or '').strip()
        display_name = (request.POST.get('display_name') or '').strip()
        position = (request.POST.get('position') or '').strip()
        context.update({
            'form_organization': organization,
            'form_display_name': display_name,
            'form_position': position,
            'saved': False,
        })

        errors = []
        row_errors = {}
        if len(organization) > 180 or len(display_name) > 150 or len(position) > 100:
            errors.append({'key': '', 'date': '', 'message': 'One or more header fields are too long.'})
        if not display_name:
            errors.append({'key': '', 'date': '', 'message': 'Enter the employee name before saving.'})

        valid_types = {key for key, _ in TimesheetEntry.DAY_TYPES}
        items = []
        for offset in range(count):
            current = first + timedelta(days=offset)
            key = current.strftime('%Y%m%d')
            day_type = (request.POST.get(f'type_{key}') or '').strip()
            activities = (request.POST.get(f'activities_{key}') or '').strip()
            raw_hours = (request.POST.get(f'hours_{key}') or '').strip()
            error = None
            hours = Decimal('0')

            if day_type not in valid_types and day_type != '':
                error = 'Please choose a valid day type.'
            elif not day_type:
                if raw_hours or activities:
                    error = 'Choose a day type or clear the hours and activities.'
            elif len(activities) > 8000:
                error = 'Activities must not exceed 8,000 characters.'
            elif day_type == 'WORK':
                try:
                    hours = Decimal(raw_hours)
                except (InvalidOperation, ValueError):
                    error = 'Enter working hours greater than 0 (up to 24).'
                else:
                    if (not hours.is_finite() or hours <= 0 or hours > 24
                            or hours.as_tuple().exponent < -2):
                        error = 'Working hours must be greater than 0 and up to 24 (maximum two decimals).'

            if error:
                row_errors[key] = error
                errors.append({
                    'key': key,
                    'date': current.strftime('%d %b %Y'),
                    'message': error,
                })
            elif day_type:
                items.append(TimesheetEntry(
                    user=request.user, date=current, day_type=day_type,
                    hours=hours, activities=activities,
                ))

        if errors:
            # Keep the actual POST values, including uncommitted AI drafts.
            for row in context['rows']:
                key = row['key']
                row['day_type'] = request.POST.get(f'type_{key}', '')
                row['hours'] = request.POST.get(f'hours_{key}', '')
                row['activities'] = request.POST.get(f'activities_{key}', '')
                row['error'] = row_errors.get(key, '')
            context['form_errors'] = errors
            return render(request, 'tasks/monthly_timesheet.html', context, status=422)

        with transaction.atomic():
            preference.organization = organization
            preference.display_name = display_name
            preference.position = position
            preference.save()
            TimesheetEntry.objects.filter(user=request.user, date__range=(first, last)).delete()
            TimesheetEntry.objects.bulk_create(items)
        return redirect(f"{reverse('tasks:monthly_timesheet')}?month={first:%Y-%m}&saved=1")

    return render(request, 'tasks/monthly_timesheet.html', context)


@login_required
def download_monthly_timesheet(request):
    first, last, count = _month_range(request.GET.get('month'))
    preference = TimesheetPreference.objects.filter(user=request.user).first()
    organization = preference.organization if preference else ''
    display_name = (preference.display_name if preference and preference.display_name else '') or request.user.get_full_name() or request.user.username
    position = preference.position if preference else ''
    rows = _month_rows(request.user, first, count)
    working_days = sum(row['day_type'] == 'WORK' for row in rows)

    output = BytesIO()
    book = xlsxwriter.Workbook(output, {
        'in_memory': True,
        'strings_to_formulas': False,
        'strings_to_urls': False,
    })
    sheet = book.add_worksheet('Timesheet')
    sheet.hide_gridlines(2)
    sheet.set_landscape()
    sheet.set_paper(9)  # A4
    sheet.fit_to_pages(1, 0)
    sheet.set_margins(.3, .3, .4, .4)
    sheet.set_column('A:A', 13)
    sheet.set_column('B:B', 17)
    sheet.set_column('C:C', 17)
    sheet.set_column('D:D', 100)
    sheet.freeze_panes(8, 0)

    label = book.add_format({'font_name': 'Arial', 'font_size': 11, 'bold': True})
    title = book.add_format({'font_name': 'Arial', 'font_size': 13, 'bold': True})
    meta = book.add_format({'font_name': 'Arial', 'font_size': 11})
    header = book.add_format({'font_name': 'Arial', 'font_size': 11, 'bold': True,
                              'align': 'center', 'valign': 'vcenter', 'border': 1,
                              'bg_color': '#EDEDED', 'text_wrap': True})
    day_style = book.add_format({'font_name': 'Arial', 'font_size': 10,
                                 'align': 'center', 'valign': 'vcenter', 'border': 1,
                                 'num_format': 'd-mmm'})
    center = book.add_format({'font_name': 'Arial', 'font_size': 10,
                              'align': 'center', 'valign': 'vcenter', 'border': 1})
    activity = book.add_format({'font_name': 'Arial', 'font_size': 10,
                                'valign': 'top', 'text_wrap': True, 'border': 1})
    weekend = book.add_format({'bg_color': '#9FBADB', 'border': 1})
    weekend_date = book.add_format({'bg_color': '#9FBADB', 'border': 1,
                                    'align': 'center', 'valign': 'vcenter', 'num_format': 'd-mmm'})

    sheet.merge_range('A1:D1', f'Work for: {organization}', label)
    sheet.merge_range('A2:D2', 'Timesheet', title)
    sheet.write('A4', 'Name:', label)
    sheet.merge_range('B4:D4', display_name, meta)
    sheet.write('A5', 'Position:', label)
    sheet.merge_range('B5:D5', position, meta)
    sheet.write('A6', 'Total Working Days:', label)
    sheet.write_number('B6', working_days, label)
    sheet.write('A7', 'Month/Year:', label)
    sheet.write('B7', first.strftime('%b/%Y'), label)
    sheet.set_row(7, 35)
    for i, name in enumerate(('Date', 'Working Day', 'Hours Worked', 'Task')):
        sheet.write(7, i, name, header)

    for index, row in enumerate(rows, start=8):
        day = row['date']
        is_weekend = row['weekend']
        sheet.set_row(index, 22 if is_weekend else max(26, min(100, 18 * (1 + row['activities'].count('\n')))))
        sheet.write_datetime(index, 0, day, weekend_date if is_weekend else day_style)
        day_type = row['day_type']
        sheet.write_string(index, 1, 'Yes' if day_type == 'WORK' else '', weekend if is_weekend else center)
        if day_type == 'WORK':
            sheet.write_number(index, 2, float(row['hours']), weekend if is_weekend else center)
        else:
            sheet.write_blank(index, 2, None, weekend if is_weekend else center)
        notes = row['activities']
        if day_type != 'WORK' and day_type:
            label_text = dict(TimesheetEntry.DAY_TYPES).get(day_type, day_type)
            notes = f'{label_text}\n{notes}'.strip() if notes else label_text
        sheet.write_string(index, 3, notes, weekend if is_weekend else activity)

    sheet.print_area(0, 0, 7 + count, 3)
    sheet.repeat_rows(7)
    book.close()
    output.seek(0)
    response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Timesheet_{first:%Y_%m}.xlsx"'
    response['Cache-Control'] = 'private, no-store'
    return response
