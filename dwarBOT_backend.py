"""Данный код описывает программный алгоритм бота для браузерной
онлайн-игры Легенда: Наследие Драконов. Бот предназначен для
автоматического гринда игровых существ"""

import numpy as np  # Используется в алгоритме поиска совпадений OpenCV
import pyautogui as pg  # Для автоматизации действий мыши
import cv2  # Для распознавания изображений на экране
import configparser  # Для связи программы с конфигурационным файлом
from time import sleep  # Для создания пауз в работе программы
from PIL import ImageGrab  # Для создания и сохранения скриншотов экрана (для OpenCV)
from pytesseract import image_to_string  # Для распознавания экранного текста

# Переменные для хранения изображений-шаблонов (для сравнения через OpenCV)
TEMP_IMAGE_1 = cv2.imread('images/win_image.png', 0)
TEMP_IMAGE_2 = cv2.imread('images/hit_image.png', 0)
TEMP_IMAGE_3 = cv2.imread('images/busy_creature.png', 0)
TEMP_IMAGE_4 = cv2.imread('images/defeat_image.png', 0)
# Переменные для хранения текстовых шаблонов (для сравнения через tesseract)
ERROR_TEXT1 = 'Цель еще не восстановилась!'
ERROR_TEXT2 = 'Не удалось выполнить действие "Напасть на монстра"!'
ERROR_TEXT3 = 'Выберите объект действия'
SEARCH_TEXT1 = 'выход'

# Определяет режим блока в бою (0 - не в блоке, 1 - в блоке)
block_value = 0
# Переменная для хранения координат лечебных эликсиров (в бою pyautogui кликает по ним)
elixirs = []
# Переменная для хранения координат для вызова ездового животного (помощь в бою)
helpers = []

# Хранит шаблон целевого существа (для нападения)
target_creature = cv2.imread('creature_text.png', 0)

# Присвоение программным переменным дефолтного значения из файла конфигурации
config = configparser.ConfigParser()
config.read('config.ini')
# Порог хитпоинтов в бою, ниже которого программа будет применять эликсиры
min_hp_in_fight = int(config['options']['min_hp_in_fight'])
# Порог противников в бою, выше которого программа вызовет ездовое животное
max_creature_without_help = int(config['options']['max_creature_without_help'])
# Порог хитпоинтов в бою, ниже которого программа встанет в блок (режим защиты)
max_hp_without_block = int(config['options']['max_hp_without_block'])
# Переменная задержки действий. Увеличивает продолжительности time.sleep() по всей программе
delay_factor = float(config['options']['delay_factor'])

# Хранит последовательность для суперудара в бою
hit_list = config['hits_seq']['hit_list'].split(', ')

# Блок для адаптации всех координат (для pyautogui) под текущее разрешение экрана
PROGRAM_RESOLUTION = (1920, 1080)
current_resolution = pg.size()
# Коэффициенты приведения координат к текущему разрешению.
xrf = current_resolution[0]/PROGRAM_RESOLUTION[0]
yrf = current_resolution[1]/PROGRAM_RESOLUTION[1]

# Переменная для функции запуска/остановки программы
work = True


def image_analyze(base_image, x1, y1, x2, y2, threshold, mode):  # Функция анализа изображения с помощью OpenCV
    """
    Функция для проверки текущего изображения на наличие шаблонов внутри.
    Для поиска шаблонов используется OpenCV.

    :param base_image: Шаблон (то, что ищем)
    :param x1: Координата X первой точки для скриншота
    :param y1: Координата Y первой точки для скриншота
    :param x2: Координата X второй точки для скриншота
    :param y2: Координата Y второй точки для скриншота
    :param threshold: Порог соответствия скриншота шаблону
    :param mode: Выбор режима функции (xy - определение координаты, tf - проверка на наличие)
    :return: В режиме xy вернёт список координат [x, y], в режиме tf вернёт True/False
    """
    # Создание, сохранение и перевод скриншота в формат для OpenCV
    screen = ImageGrab.grab(bbox=(x1, y1, x2, y2))
    screen.save('images/base_screen.png')
    rgb = cv2.imread('images/base_screen.png')
    gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)
    # Поиск шаблона в текущем скриншоте
    res = cv2.matchTemplate(gray, base_image, cv2.TM_CCOEFF_NORMED)
    loc = np.where(res >= threshold)
    # Проверка режима функции
    if mode == 'xy':
        # Получение координат места нахождения шаблона в скриншоте
        x, y = (0, 0)
        for pt in zip(*loc[::-1]):
            x = int(pt[0])
            y = int(pt[1])
        x += (202*xrf)
        y += (270*yrf)
        return [x, y]
    elif mode == 'tf':
        # Проверка на наличие шаблона внутри скриншота
        if np.any(loc):
            return True
        else:
            return False


def text_recognition(x1, y1, x2, y2, search_text, mode):  # Функция анализа экранного текста с помощью tesseract
    """
    Функция для распознавания экранного текста на скриншоте.
    Для распознавания используется tesseract.

    :param x1: Координата X первой точки для скриншота
    :param y1: Координата Y первой точки для скриншота
    :param x2: Координата X второй точки для скриншота
    :param y2: Координата Y второй точки для скриншота
    :param search_text: Текстовый шаблон (то, что ищем). В режиме int задавать пустую строку.
    :param mode: Выбор режима функции (str - распознавание текста, int - распознавание целого числа)
    :return: В режиме str вернёт True/False, в режиме int вернёт распознанное целое число.
    """
    # Создание скриншота с текстом
    screen = ImageGrab.grab(bbox=(x1, y1, x2, y2))
    # Проверка режима функции
    if mode == 'str':
        # Проверка на соответствие текстовому шаблону
        text = image_to_string(screen, lang='rus', config=r'--oem 3 --psm 13')
        text = text.split('\n')[0]
        try:
            if text == search_text:
                return True
            else:
                return False
        except ValueError:
            return False
    elif mode == 'int':
        # Распознование числа на скриншоте
        text = image_to_string(screen, config=r'--oem 3 --psm 13')
        text = text.split('/')[0]
        text = text.split('\n')[0]
        # Перехват исключения, в случае некорректного распознавания числа
        try:
            return int(text)
        except ValueError:
            return 600


def fight_status_exam():  # Функция получения статуса боя
    """
    На основе функций анализа изображения и распознавания текста
    определяет в каком состоянии находится текущий бой.

    :return: Возвращает строку (hit - наш ход, win - бой окончен победой, defeat - бой окончен поражением)
    """
    # Бесконечный цикл получения получения статуса боя(прервется в случае попадания в один из вариантов)
    while True:
        if image_analyze(TEMP_IMAGE_2, 469*xrf, 399*yrf, 493*xrf, 433*yrf, 0.7, 'tf'):
            return 'hit'
        # Проверка появления в области боя кнопки "выход"(появляется при любом окончании боя)
        elif text_recognition(525*xrf, 416*yrf, 565*xrf, 427*yrf, SEARCH_TEXT1, 'str'):
            # Провека, как окончился бой (это влияет на дальнейшие действия)
            if image_analyze(TEMP_IMAGE_1, 407*xrf, 301*yrf, 689*xrf, 429*yrf, 0.7, 'tf'):
                return 'win'
            elif image_analyze(TEMP_IMAGE_4, 407*xrf, 301*yrf, 689*xrf, 429*yrf, 0.7, 'tf'):
                resurrection()
                return 'defeat'


def stand_block():  # Функция управления режимом блока
    """
    С помощью функции распознавания текста определяет кол-во текущих hitpoints,
    и на основании этого принимает решение о необходимости включения/выключения режима блока.

    :return: -
    """
    global block_value
    # Проверка текущих hp и переменной block_value (0 - не в блоке, 1 - в блоке)
    if text_recognition(349*xrf, 229*yrf, 385*xrf, 242*yrf, '', 'int') < max_hp_without_block and block_value == 0:
        # Встать в блок
        pg.leftClick(428*xrf, 418*yrf)
        block_value = 1
    elif text_recognition(349*xrf, 229*yrf, 385*xrf, 242*yrf, '', 'int') > max_hp_without_block and block_value == 1:
        # Выйти из блока
        pg.leftClick(428*xrf, 418*yrf)
        block_value = 0


def use_elixir():  # Функция управления эликсирами восстановления hp
    """
    С помощью функции распознавания текста определяет кол-во текущих hitpoints,
    и на основании этого принимает решение о необходимости использования эликсиров
    для восстановления hitpoints.

    :return: -
    """
    global elixirs
    # Проверка текущих hp
    if text_recognition(349*xrf, 229*yrf, 385*xrf, 242*yrf, '', 'int') < min_hp_in_fight:
        # Проверка наличия эликсиров в кармане (через список с координатами их активации)
        if elixirs:
            # Цикл последовательного нажатия на координаты для применения эликсира (иногда нужно несколько кликов)
            for q in elixirs[0]:
                pg.leftClick(q)
                sleep(0.2)
            # Удаление использованного эликсира из списка
            del elixirs[0]
            # Пауза на восстановление (эликсир восстанавливает hp в течении определенного времени)
            sleep(12)


def hit(direction):  # Функция нанесения ударов
    """
    Наносит удар в соответствии с выбранным направлением.

    :param direction: Направление удара (в игре их три: вверх, вперед, вниз)
    :return: -
    """
    # Проверка переданного аргумента (направления удара)
    if direction == 'forward':
        pg.leftClick(541*xrf, 420*yrf)
    elif direction == 'down':
        pg.leftClick(512*xrf, 471*yrf)
    elif direction == 'up':
        pg.leftClick(511*xrf, 372*yrf)
    sleep(1+delay_factor*2)


def help_exam():  # Функция управления призывом ездового животного.
    """
    С помощью функции распознавания текста определяет кол-во текущих врагов (через цифру на экране),
    и на основании этого принимает решение о необходимости вызова ездового животного.
    Координаты для вызова ездового находятся в списке helpers

    :return: -
    """
    global helpers
    # Проверка кол-ва врагов в бою и возможности вызова ездового (дважды вызвать нельзя)
    if text_recognition(1168 * xrf, 233 * yrf, 1181 * xrf, 247 * yrf, '', 'int') > max_creature_without_help and \
            len(helpers) > 0:
        # Цикл последовательного нажатия на координаты для вызова (нужно несколько кликов)
        for i in helpers[0]:
            sleep(1)
            pg.leftClick(i)
        # Удаление перечня координат из списка
        del helpers[0]


def press_hunt():  # Функция вызова режима охоты
    """
    Делает клик по кнопке вызова окна охоты.

    :return: -
    """
    sleep(0.5+delay_factor*0.5)
    pg.leftClick(938*xrf, 136*yrf)
    sleep(2+delay_factor*2)


def eat_hp():  # Функция восстановления hipoints после боя
    """
    Воспроизводит последовательность кликов, необходимую
    для восстановления hp после боя.

    :return: -
    """
    sleep(0.2+delay_factor*0.8)
    pg.leftClick(1875*xrf, 56*yrf)
    sleep(0.2 + delay_factor * 0.8)
    pg.leftClick(1804*xrf, 101*yrf)
    sleep(0.2+delay_factor*0.8)


def resurrection():  # Функция возрождения после проигранного боя
    """
    Воспроизводит последовательность кликов, необходимую
    для возрождения после проигранного боя.

    :return: -
    """
    pg.leftClick(886*xrf, 133*yrf)
    sleep(2+delay_factor*2)
    pg.leftClick(684*xrf, 308*yrf)
    sleep(0.3+delay_factor*0.7)


def bot_start():  # Основная функция программы
    """
    Выполняет последовательность действий для непрерывного
    гринда внутриигровых монтров.
    Работает пока глобальная переменная work - истина

    :return: -
    """
    global block_value, elixirs, helpers, work
    work = True
    sleep(3)
    # Основной программный цикл
    while work:
        # Переменные координаты цели нападения
        target_x, target_y = 0, 0
        # Цикл поиска цели для нападения
        while work:
            press_hunt()
            # Определение координаты монстра для нападения
            target_x, target_y = image_analyze(target_creature, 202*xrf, 270*yrf, 1702*xrf, 745*yrf, 0.9, 'xy')
            # Условие передачи нулевых координат (если распознавание сработало некорректно)
            if target_x == 202*xrf and target_y == 270*yrf:
                continue
            else:
                break
        # Совершение кликов для нападения на цель
        pg.leftClick((target_x+(54*xrf)), (target_y-(25*yrf)))
        sleep(0.5)
        pg.leftClick(615*xrf, 226*yrf)
        sleep(1)
        # Проверка и отработка различных всплывающих ошибок нападения
        if image_analyze(TEMP_IMAGE_3, 796*xrf, 481*yrf, 1124*xrf, 624*yrf, 0.8, 'tf'):
            pg.leftClick(1044*xrf, 579*yrf)
            continue
        elif text_recognition(872*xrf, 459*yrf, 1050*xrf, 474*yrf, ERROR_TEXT1, 'str') or \
                text_recognition(791*xrf, 454*yrf, 1133*xrf, 477*yrf, ERROR_TEXT2, 'str'):
            pg.leftClick(963*xrf, 514*yrf)
            continue
        elif text_recognition(665*xrf, 227*yrf, 810*xrf, 240*yrf, ERROR_TEXT3, 'str'):
            continue
        # Обновление переменных перед началом боя (необходимо обновлять перед каждым боем)
        block_value = 0
        elixirs = [((38*xrf, 221*yrf),),
                   ((38*xrf, 266*yrf),),
                   ((38*xrf, 308*yrf),),
                   ((38*xrf, 353*yrf),),
                   ((38*xrf, 395*yrf),),
                   ((38*xrf, 440*yrf),),
                   ((55*xrf, 471*yrf), (38*xrf, 221*yrf), (15*xrf, 471*yrf)),
                   ((55*xrf, 471*yrf), (38*xrf, 266*yrf), (15*xrf, 471*yrf))]
        helpers = [((1885*xrf, 307*yrf), (263*xrf, 187*yrf)), ]
        fight_status = 0
        sleep(1+delay_factor*3)
        # Цикл проведения боя
        while work:
            # Переменная для учёта номера текущего удара в последовательности
            hit_value = len(hit_list)
            # Цикл нанесения ударов (перебирает список с последовательностью)
            for i in hit_list:
                # Получения статуса боя
                fight_status = fight_status_exam()
                # Оценка статуса боя
                if fight_status == 'hit':
                    # Условие для выхода из режима блока перед супер-ударом (последний в последовательности)
                    if hit_value == 1:
                        if block_value == 1:
                            stand_block()
                    # Условие для обычного удара
                    else:
                        stand_block()
                    # Восполение здоровья, если это необходимо
                    use_elixir()
                    # Нанесение соответствующего удара
                    hit(i)
                # Условие выхода из боя с победой
                elif fight_status == 'win':
                    break
                # Условие выхода из боя с поражением
                elif fight_status == 'defeat':
                    break
                # Учёт нанесенного удара (приближение переменной учёта к суперудару)
                hit_value -= 1
            # Условие для естественного выхода из цикла (бой продолжается)
            else:
                # Вызов ездового животного, при необходимости
                help_exam()
                # Повторение цикла боя
                continue
            # Разрушение цикла боя (произойдет при победе или поражении)
            break
        # Проверка выхода из боя с поражением (для дальнейшего возрождения)
        if fight_status == 'defeat':
            resurrection()
        # Восстановления hitpoints перед следующим боем
        eat_hp()
        continue


def bot_stop():  # Функция для остановки программы
    """
    Останавливает работу программы путем изменения переменной
    work.

    :return: -
    """
    global work
    work = False


# Проверка прямого запуска кода
if __name__ == '__main__':
    bot_start()
