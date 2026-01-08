import pandas as pd
import random
from faker import Faker

# Initialize Faker for generating fake names and dates
fake = Faker('ru_RU')

# Define number of rows
num_rows = 60000

# Generate data
data = {
    'СЕРИЯ номер паспорта': [f"{random.randint(1000, 9999)} {random.randint(100000, 999999)}" for _ in range(num_rows)],
    '№ п/п': list(range(1, num_rows + 1)),
    'Фамилия': [fake.last_name() for _ in range(num_rows)],
    'Имя': [fake.first_name() for _ in range(num_rows)],
    'Отчество': [fake.middle_name() for _ in range(num_rows)],
    'Дата рождения': [
        f"{d.month}/{d.day}/{d.year}"  # manual format: M/D/YYYY
        for d in (fake.date_of_birth(minimum_age=18, maximum_age=80) for _ in range(num_rows))
    ]
}

# Create a DataFrame
df = pd.DataFrame(data)

# Save to Excel
output_file = 'База_big.xlsx'
df.to_excel(output_file, index=False)

print(f"Excel file '{output_file}' generated with {num_rows} rows.")