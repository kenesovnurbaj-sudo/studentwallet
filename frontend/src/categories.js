const translations = {
  'Еда': 'Food',
  'Транспорт': 'Transport',
  'Жильё': 'Housing',
  'Жилье': 'Housing',
  'Учёба': 'Study',
  'Учеба': 'Study',
  'Развлечения': 'Entertainment',
  'Здоровье': 'Health',
  'Покупки': 'Shopping',
  'Сбережения': 'Savings',
  'Другое': 'Other',
  'Прочее': 'Other',
  'Подписки': 'Subscriptions',
}

export function categoryName(name) {
  return translations[name] || name || 'Uncategorized'
}