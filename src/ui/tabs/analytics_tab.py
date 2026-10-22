"""Вкладка аналитики с графиками.

Реализует визуализацию данных:
- Распределение сотрудников по отделам
- Динамика зарплат
- Статусы проектов
- Сводная статистика
"""

import os
import logging

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QGroupBox,
    QGridLayout,
    QScrollArea,
    QFrame,
    QSpinBox,
    QMessageBox,
    QFileDialog,
)

from ui.base_tab import BaseTab
from services.analytics_service import AnalyticsService
from core.permissions import Permission
from core.exceptions import PermissionDeniedError
from styles import BUTTON_STYLES


class AnalyticsTab(BaseTab):
    """Вкладка аналитики и визуализации данных.
    
    Отображает графики:
    - Круговая диаграмма сотрудников по отделам
    - Столбчатая диаграмма средней зарплаты
    - Статистика проектов
    - Динамика найма
    """
    
    BUTTON_PERMISSIONS = {
        'btn_export_chart': Permission.EXPORT_DATA,
    }

    CUSTOM_STYLE = {
        'axes.facecolor': '#f8f9fa',
        'axes.edgecolor': '#2c3e50',
        'axes.labelcolor': '#2c3e50',
        'xtick.color': '#34495e',
        'ytick.color': '#34495e',
        'axes.titlecolor': '#2c3e50',
        'axes.titlesize': 14,
        'axes.labelsize': 12,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'font.family': 'DejaVu Sans',
        'grid.color': '#d6dbdf',
        'grid.alpha': 0.5,
        'figure.facecolor': '#ffffff'
    }

    def __init__(
        self, 
        analytics_service: AnalyticsService,
        user: dict
    ):
        """
        Args:
            analytics_service: Сервис аналитики
            user: Данные текущего пользователя
        """
        super().__init__(analytics_service, user)
        self.analytics_service = analytics_service
        self.data_loaded = False
        
        self.init_ui()
        self.setup_access_control()
        self.load_data()

    def init_ui(self):
        """Инициализирует интерфейс вкладки."""
        main_layout = QVBoxLayout()
        
        # Панель управления
        control_panel = self._create_control_panel()
        main_layout.addLayout(control_panel)
        
        # Область прокрутки для графиков
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        # Контейнер для графиков
        charts_widget = QWidget()
        charts_layout = QGridLayout()
        charts_layout.setSpacing(20)
        
        # Создание графиков
        self.employees_chart = self._create_chart_group(
            "Сотрудники по отделам",
            self._create_pie_canvas()
        )
        self.salary_chart = self._create_chart_group(
            "Средняя зарплата по отделам",
            self._create_bar_canvas()
        )
        self.projects_chart = self._create_chart_group(
            "Статусы проектов",
            self._create_pie_canvas_projects()
        )
        self.hiring_chart = self._create_chart_group(
            "Динамика найма",
            self._create_line_canvas()
        )
        
        # Размещение графиков в сетке 2x2
        charts_layout.addWidget(self.employees_chart, 0, 0)
        charts_layout.addWidget(self.salary_chart, 0, 1)
        charts_layout.addWidget(self.projects_chart, 1, 0)
        charts_layout.addWidget(self.hiring_chart, 1, 1)
        
        charts_widget.setLayout(charts_layout)
        scroll.setWidget(charts_widget)
        
        main_layout.addWidget(scroll)
        
        self.setLayout(main_layout)
        
        # Подключение сигналов
        self._connect_signals()

    def _create_control_panel(self) -> QHBoxLayout:
        """Создает панель управления."""
        panel = QHBoxLayout()
        
        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.setStyleSheet(BUTTON_STYLES.get("primary", ""))

        self.btn_export_chart = QPushButton("Экспорт")
        self.btn_export_chart.setStyleSheet(BUTTON_STYLES.get("export", ""))
        
        panel.addWidget(QLabel("Период динамики (месяцев):"))
        
        self.months_spin = QSpinBox()
        self.months_spin.setRange(3, 36)
        self.months_spin.setValue(12)
        panel.addWidget(self.months_spin)
        
        panel.addWidget(self.btn_export_chart)
        panel.addWidget(self.btn_refresh)
        panel.addStretch()
        
        return panel

    def _create_chart_group(self, title: str, canvas: FigureCanvas) -> QGroupBox:
        """Создает группу с графиком."""
        group = QGroupBox(title)
        layout = QVBoxLayout()
        layout.addWidget(canvas)
        group.setLayout(layout)
        group.setMinimumSize(450, 350)
        return group

    def _create_pie_canvas(self) -> FigureCanvas:
        """Создает canvas для круговой диаграммы сотрудников."""
        self.fig_employees = Figure(figsize=(5, 4), dpi=100)
        self.ax_employees = self.fig_employees.add_subplot(111)
        canvas = FigureCanvas(self.fig_employees)
        return canvas

    def _create_bar_canvas(self) -> FigureCanvas:
        """Создает canvas для столбчатой диаграммы зарплат."""
        self.fig_salary = Figure(figsize=(5, 4), dpi=100)
        self.ax_salary = self.fig_salary.add_subplot(111)
        canvas = FigureCanvas(self.fig_salary)
        return canvas

    def _create_pie_canvas_projects(self) -> FigureCanvas:
        """Создает canvas для круговой диаграммы проектов."""
        self.fig_projects = Figure(figsize=(5, 4), dpi=100)
        self.ax_projects = self.fig_projects.add_subplot(111)
        canvas = FigureCanvas(self.fig_projects)
        return canvas

    def _create_line_canvas(self) -> FigureCanvas:
        """Создает canvas для линейного графика найма."""
        self.fig_hiring = Figure(figsize=(5, 4), dpi=100)
        self.ax_hiring = self.fig_hiring.add_subplot(111)
        canvas = FigureCanvas(self.fig_hiring)
        return canvas

    def _connect_signals(self):
        """Подключает сигналы к слотам."""
        self.btn_refresh.clicked.connect(self.safe_refresh_data)
        self.btn_export_chart.clicked.connect(self.safe_export_chart)
        self.months_spin.valueChanged.connect(self.plot_hiring)

    def apply_custom_style(self):
        """Применяет кастомный стиль matplotlib."""
        plt.rcParams.update(self.CUSTOM_STYLE)
        plt.rcParams['axes.unicode_minus'] = False

    def load_data(self):
        """Загружает данные и обновляет графики."""
        try:
            self.apply_custom_style()
            self.plot_employees()
            self.plot_salary()
            self.plot_projects()
            self.plot_hiring()
            self.data_loaded = True
        except PermissionDeniedError as e:
            self.show_error("Доступ запрещен", str(e))
        except Exception as e:
            logging.error(f"Ошибка загрузки аналитики: {e}")
            self.show_error("Ошибка", "Не удалось загрузить данные аналитики")

    def safe_refresh_data(self):
        """Обновляет данные и перерисовывает графики."""
        try:
            self.load_data()
            QMessageBox.information(self, "Обновлено", "Данные успешно обновлены")
        except Exception as e:
            logging.error(f"Ошибка обновления аналитики: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка обновления данных:\n{str(e)}")

    def safe_export_chart(self):
        """Экспортирует активный график в файл."""
        try:
            if not hasattr(self, 'fig_employees'):
                QMessageBox.warning(self, "Ошибка", "Нет графика для экспорта")
                return

            file_path, selected_filter = QFileDialog.getSaveFileName(
                self,
                "Экспорт графика",
                os.path.expanduser("~/analytics_chart"),
                "PNG (*.png);;PDF (*.pdf);;SVG (*.svg);;JPEG (*.jpg *.jpeg)"
            )
            if not file_path:
                return

            ext = selected_filter.split(' ')[0].lower()
            figure = self.fig_employees
            figure.savefig(
                file_path,
                dpi=300,
                bbox_inches='tight',
                facecolor=figure.get_facecolor(),
                format='jpeg' if ext == 'jpeg' else ext
            )
            QMessageBox.information(self, "Успех", f"График экспортирован:\n{file_path}")
        except Exception as e:
            logging.error(f"Ошибка экспорта: {str(e)}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта:\n{str(e)}")

    def plot_employees(self):
        """Строит диаграмму сотрудников по отделам."""
        try:
            data = self.analytics_service.get_employee_department(self.user)
            
            self.ax_employees.clear()
            
            if data:
                labels = [d['department_name'] for d in data]
                sizes = [d['count'] for d in data]
                
                colors = plt.cm.Set3(range(len(data)))
                
                wedges, texts, autotexts = self.ax_employees.pie(
                    sizes, 
                    labels=labels if len(labels) <= 6 else None,
                    autopct='%1.1f%%',
                    colors=colors,
                    startangle=90
                )
                
                if len(labels) > 6:
                    self.ax_employees.legend(
                        wedges, labels,
                        title="Отделы",
                        loc="center left",
                        bbox_to_anchor=(1, 0, 0.5, 1),
                        fontsize=8
                    )
                
                self.ax_employees.set_title("Распределение сотрудников")
            else:
                self.ax_employees.text(0.5, 0.5, 'Нет данных', 
                                       ha='center', va='center')
            
            self.fig_employees.tight_layout()
            self.fig_employees.canvas.draw()
            
        except Exception as e:
            logging.error(f"Ошибка построения диаграммы сотрудников: {e}")

    def plot_salary(self):
        """Строит диаграмму средней зарплаты по отделам."""
        try:
            data = self.analytics_service.get_average_salary_by_department(self.user)
            
            self.ax_salary.clear()
            
            if data:
                departments = [d['department_name'][:15] for d in data]
                salaries = [d['avg_salary'] for d in data]
                
                bars = self.ax_salary.barh(departments, salaries, color='#1976d2')
                self.ax_salary.set_xlabel('Средняя зарплата, ₽')
                self.ax_salary.set_title('Средняя зарплата по отделам')
                
                for bar, salary in zip(bars, salaries):
                    width = bar.get_width()
                    self.ax_salary.text(
                        width, bar.get_y() + bar.get_height()/2,
                        f' {salary:,.0f}',
                        ha='left', va='center', fontsize=8
                    )
            else:
                self.ax_salary.text(0.5, 0.5, 'Нет данных', 
                                    ha='center', va='center')
            
            self.fig_salary.tight_layout()
            self.fig_salary.canvas.draw()
            
        except Exception as e:
            logging.error(f"Ошибка построения диаграммы зарплат: {e}")

    def plot_projects(self):
        """Строит диаграмму статусов проектов."""
        try:
            data = self.analytics_service.get_projects_by_status(self.user)
            
            self.ax_projects.clear()
            
            if data:
                labels = [d['status'] for d in data]
                sizes = [d['count'] for d in data]
                
                status_colors = {
                    'Планирование': '#17a2b8',
                    'В работе': '#28a745',
                    'Приостановлен': '#ffc107',
                    'Завершен': '#6c757d',
                    'Отменен': '#dc3545'
                }
                colors = [status_colors.get(label, '#999999') for label in labels]
                
                wedges, texts, autotexts = self.ax_projects.pie(
                    sizes, 
                    labels=labels,
                    autopct='%1.1f%%',
                    colors=colors,
                    startangle=90
                )
                
                self.ax_projects.set_title("Статусы проектов")
            else:
                self.ax_projects.text(0.5, 0.5, 'Нет данных', 
                                      ha='center', va='center')
            
            self.fig_projects.tight_layout()
            self.fig_projects.canvas.draw()
            
        except Exception as e:
            logging.error(f"Ошибка построения диаграммы проектов: {e}")

    def plot_hiring(self):
        """Строит график динамики найма."""
        try:
            months = self.months_spin.value()
            data = self.analytics_service.get_hiring_dynamics(self.user, months)
            
            self.ax_hiring.clear()
            
            if data:
                months_labels = [d['month'] for d in data]
                counts = [d['hired_count'] for d in data]
                
                self.ax_hiring.plot(
                    months_labels, counts, 
                    marker='o', linewidth=2, color='#1976d2'
                )
                self.ax_hiring.fill_between(
                    months_labels, counts, 
                    alpha=0.3, color='#1976d2'
                )
                
                self.ax_hiring.set_xlabel('Месяц')
                self.ax_hiring.set_ylabel('Принято сотрудников')
                self.ax_hiring.set_title('Динамика найма')
                
                plt.setp(self.ax_hiring.xaxis.get_majorticklabels(), rotation=45)
                
                self.ax_hiring.grid(True, alpha=0.3)
            else:
                self.ax_hiring.text(0.5, 0.5, 'Нет данных', 
                                    ha='center', va='center')
            
            self.fig_hiring.tight_layout()
            self.fig_hiring.canvas.draw()
            
        except Exception as e:
            logging.error(f"Ошибка построения графика найма: {e}")

    def _get_export_filename(self, extension: str) -> str:
        return f"analytics_report.{extension}"

    def _get_export_title(self) -> str:
        return "Аналитический отчет"
