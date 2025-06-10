# -------------------------------------------
#   config reader
# -------------------------------------------

def datatype(value: str):
    try:
        return int(value)
    except ValueError:
        pass
    value = value.removeprefix('"').removesuffix('"')
    value = value.removeprefix("'").removesuffix("'")
    if value == "True":
        return True
    elif value == "False":
        return False
    return value


def formater(value: str):
    if value.startswith("["):
        li_formated = []
        value = value.removeprefix("[").removesuffix("]")
        li = value.split(",")
        for i in range(len(li)):
            li[i] = li[i].strip(" ")
            li_formated.append(datatype(li[i]))
        return li_formated
    return datatype(value)


def pre_formater(data: str):
    data = data.removesuffix("\n")
    if "#" in data:
        data = data[:data.find("#")]

    data = formater(data.strip(" "))
    return data


def creat_dict(data: list):
    di = {}
    name = data[0].removesuffix("{\n").rstrip(" ")
    for i in data[1:]:
        li = i.split("=")
        di[li[0].strip(" ").rstrip(" ")] = pre_formater(li[1])
    return name, di


def conf_reader(file: str):
# def conf_reader(file: str) -> dict:
    di = {}
    conf_data = []
    with open(file, "r") as conf:
        for i in conf:
            if i == "\n":
                continue
            if i.strip(" ").startswith("#"):
                continue
            conf_data.append(i)

    start = 0
    in_dict = False
    for n, i in enumerate(conf_data):
        if "{" in i:
            start = n
            in_dict = True
        elif "}" in i:
            name, mini_di = creat_dict(conf_data[start:n])
            di[name] = mini_di
            in_dict = False
        else:
            if not in_dict:
                li = i.split("=")
                di[li[0].rstrip(" ")] = formater(li[1].strip(" ").removesuffix("\n"))

    return di
