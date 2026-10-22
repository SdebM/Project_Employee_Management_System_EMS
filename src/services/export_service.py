"""Сервис экспорта данных.

Слой сервисов НЕ зависит от PyQt6: вместо живого QTableWidget
принимается снимок данных (utils.table_snapshot.TableSnapshot),
совместимый по интерфейсу с QTableWidget. Снимок создаётся в GUI-потоке
и безопасно передаётся в фоновый QThread.
"""

import logging

from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm

import pandas as pd

from core.permissions import Permission, check_permission



class PDFExporter:
    """Класс для экспорта данных таблицы в PDF-формат."""

    @staticmethod
    def export_to_pdf(table, file_path: str, document_title: str) -> bool:
        """Экспортирует таблицу (QTableWidget или TableSnapshot) в PDF."""
        if table.rowCount() == 0:
                raise ValueError("Нет данных для экспорта")

        font_name = PDFExporter.register_fonts()
        styles = PDFExporter.create_styles(font_name)
        headers, table_data = PDFExporter.prepare_data(table, styles)

        doc = SimpleDocTemplate(
                file_path,
                pagesize=landscape(A4),
                leftMargin=10 * mm,
                rightMargin=10 * mm,
                topMargin=15 * mm,
                bottomMargin=15 * mm
            )

        elements = []
        elements.append(Paragraph(document_title, styles['Title']))
        elements.append(Spacer(1, 0.2 * 25.4))

        table_obj = Table(
            table_data,
            colWidths=PDFExporter.calculate_column_widths(len(headers))
        )
        table_obj.setStyle(PDFExporter.create_table_style(font_name))

        elements.append(table_obj)
        doc.build(elements)
        return True

            
    @staticmethod
    def prepare_data(table, styles):
        def format_text(text, is_header=False):
            style = styles['Header'] if is_header else styles['Body']
            text = str(text).strip() if text else ""
            return Paragraph(f"<b>{text}</b>" if is_header else text, style)

        headers = [
            table.horizontalHeaderItem(i).text()
            for i in range(table.columnCount())
        ]

        table_data = []
        if headers:
            table_data.append([format_text(h, True) for h in headers])

        for row in range(table.rowCount()):
            formatted_row = []
            for col in range(table.columnCount()):
                item = table.item(row, col)
                text = item.text() if item else ""
                formatted_row.append(format_text(text))
            table_data.append(formatted_row)

        return headers, table_data

    @staticmethod
    def create_styles(font_name):
        styles = getSampleStyleSheet()

        styles.add(ParagraphStyle(
            name='Header',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=9,
            leading=11,
            alignment=1,
            textColor=colors.white,
            spaceBefore=2,
            spaceAfter=2
        ))

        styles.add(ParagraphStyle(
            name='Body',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=8,
            leading=10,
            alignment=1,
            textColor=colors.black,
            spaceBefore=2,
            spaceAfter=2
        ))

        styles['Title'].fontName = font_name
        styles['Title'].fontSize = 14
        styles['Title'].alignment = 1

        return styles

    @staticmethod
    def create_table_style(font_name):
        return TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ])

    @staticmethod
    def register_fonts():
        font_name = 'Helvetica'
        try:
            pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
            font_name = 'DejaVuSans'
        except Exception:
            try:
                pdfmetrics.registerFont(TTFont('Arial', 'Arial.ttf'))
                font_name = 'Arial'
            except Exception:
                logging.warning("Используется стандартный шрифт")
        return font_name

    @staticmethod
    def calculate_column_widths(columns_count):
        page_width = landscape(A4)[0] - 20 * mm
        return [page_width / columns_count * 0.95] * columns_count


class ExcelExporter:
    """Класс для экспорта данных таблицы в Excel-формат."""

    @staticmethod
    def export_to_excel(table, file_path: str, sheet_name: str = "Данные") -> bool:
        """Экспортирует таблицу (QTableWidget или TableSnapshot) в Excel."""
        if table.rowCount() == 0:
            raise ValueError("Нет данных для экспорта")

        headers = [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
        data = []
        for row in range(table.rowCount()):
            row_data = [table.item(row, col).text() if table.item(row, col) else "" for col in range(table.columnCount())]
            data.append(row_data)

        df = pd.DataFrame(data, columns=headers)
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        return True


class ExportService:
    @staticmethod
    def check_export_permission(user: dict) -> bool:
        try:
            check_permission(user, Permission.EXPORT_DATA)
            return True
        except Exception:
            return False

    @staticmethod
    def export_to_pdf(table, file_path: str, document_title: str) -> bool:
        """Экспортирует таблицу (QTableWidget или TableSnapshot) в PDF."""
        return PDFExporter.export_to_pdf(table, file_path, document_title)

    @staticmethod
    def export_to_excel(table, file_path: str, sheet_name: str = "Данные") -> bool:
        """Экспортирует таблицу (QTableWidget или TableSnapshot) в Excel."""
        return ExcelExporter.export_to_excel(table, file_path, sheet_name)
