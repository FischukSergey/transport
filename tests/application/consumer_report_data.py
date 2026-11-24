from decimal import Decimal

from tests.application.point_report_data import (
    FACT_SURCHARGE,
    FACT_TRANSPORT,
    FACT_VOLUME,
    POINT_VOLUME,
)

# Вторая точка того же потребителя: 5 × 1,00 = 5,00, спецнадбавка 5 × 0,10 = 0,50.
# Итог потребителя складывает уже округлённые итоги точек.
# 25,008 × 1,00 одним умножением дало бы 25,01, а не 25,00.
SECOND_POINT = "78-1-9"
SECOND_ADDRESS = "Литейный, 2"
SECOND_CONTRACT = "Д-4"
SECOND_VOLUME = Decimal(5)
SECOND_TRANSPORT = Decimal("5.00")
SECOND_SURCHARGE = Decimal("0.50")
CONSUMER_PLAN_VOLUME = POINT_VOLUME + SECOND_VOLUME
CONSUMER_FACT_VOLUME = FACT_VOLUME + SECOND_VOLUME
CONSUMER_FACT_TRANSPORT = FACT_TRANSPORT + SECOND_TRANSPORT
CONSUMER_FACT_SURCHARGE = FACT_SURCHARGE + SECOND_SURCHARGE
# Чужой потребитель с тем же регионом. Его 100 в итог не входят.
FOREIGN_BUYER = "000009"
FOREIGN_NAME = "Чужой"
FOREIGN_POINT = "78-1-6"
FOREIGN_ADDRESS = "Садовая, 3"
FOREIGN_CONTRACT = "Д-5"
FOREIGN_VOLUME = Decimal(100)
CONSUMER_TOTAL_TEXT = "Итого потребитель"
SHEET_TITLE = "Потребитель"
KIND_TITLE = "Промышленный"
POINT_COUNT = 2
TOTAL_ROW_COUNT = 1
SUMMARY_CODE_COLUMN = 0
SUMMARY_PLAN_COLUMN = 3
SUMMARY_FACT_COLUMN = 4
SUMMARY_TRANSPORT_COLUMN = 5
SUMMARY_SURCHARGE_COLUMN = 6
FIRST_POINT_ROW = 0
SECOND_POINT_ROW = 1
