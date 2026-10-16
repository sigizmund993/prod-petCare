from fastapi import FastAPI

app = FastAPI(title="PetCare API")

@app.post("/user/add")
def user_add(name_user: str, password: str, email: str, number: str):

@app.delete("/user/del")
def user_del(user_id: int):

@app.put("/user/edit")
def user_edit(user_: int, name_user: str, password: str, email: str, number: str):

@app.get("/user/get")
def user_get(user_id: int, name_user: str, email: str, number: str):



@app.post("/pet/add")
def pet_add(name_pet: str, owner_id: int, parody: str):

@app.delete("/pet/del")
def pet_del(pet_id: int):

@app.put("/pet/edit")
def pet_edit(pet_id: int, name_pet: str, owner_id: int, breed: str):

@app.get("/pet/get")
def pet_get(pet_id: int, name_pet: str, owner_ids: str, prop_ids: int):


@app.post("/prop/add")
def prop_add(pet_id: int, name_prop: str, text: str, rep: int, date: int, owner_id: int):

@app.delete("/prop/del")
def prop_del(prop_id: int):

@app.put("/prop/edit")
def prop_edit(prop_id: int, pet_id: int, name_prop: str, text: str, rep: int, date: int, owner_id: int):

@app.get("/prop/get")
def prop_get(prop_id: int, pet_id: int, name_prop: str, text: str, rep: int, date: int, owner_id: int):