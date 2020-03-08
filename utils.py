from keras.layers import *
from keras.models import Sequential
import numpy as np
import matplotlib.pyplot as plt
import gc, sys,os

def compare_hist_train(hist1,hist2, dataset_name=""):
    ### binary vs traditional
    history_dict1 = hist1.history
    history_dict2 = hist2.history
    loss_values1 = history_dict1['loss']
    val_loss_values1 = history_dict1['val_loss']
    loss_values2 = history_dict2['loss']
    val_loss_values2 = history_dict2['val_loss']
    epochs_l = range(1, len(loss_values1) + 1)

    plt.figure(figsize=(15,6))
    plt.plot(epochs_l, loss_values1, 'bo-', label = "Train set traditional")
    plt.plot(epochs_l, val_loss_values1, 'bv-', label = "Val set traditional")
    plt.plot(epochs_l, loss_values2, 'go-', label = "Train set binary")
    plt.plot(epochs_l, val_loss_values2, 'gv-', label = "Val set binary")
    plt.xlabel('Epochs')
    plt.ylabel('Loss')
    plt.legend(loc="upper right", fancybox= True)
    plt.title("VAE loss "+dataset_name)
    plt.show()
    
    
def define_fit(multi_label,X,Y, epochs=20):
    #function to define and train model

    #define model
    model_FF = Sequential()
    model_FF.add(Dense(256, input_dim=X.shape[1], activation="relu"))
    #model_FF.add(Dense(128, activation="relu"))
    if multi_label:
        model_FF.add(Dense(Y.shape[1], activation="sigmoid"))
        model_FF.compile(optimizer='adam', loss="binary_crossentropy")
    else:
        model_FF.add(Dense(Y.shape[1], activation="softmax"))
        model_FF.compile(optimizer='adam', loss="categorical_crossentropy",metrics=["accuracy"])
    model_FF.fit(X, Y, epochs=epochs, batch_size=100, verbose=0)
    return model_FF


class MedianHashing(object):
    def __init__(self):
        self.threshold = None
        self.latent_dim = None
    def fit(self, X):
        self.threshold = np.median(X, axis=0)
        self.latent_dim = X.shape[1]
    def transform(self, X):
        assert(X.shape[1] == self.latent_dim)
        binary_code = np.zeros(X.shape)
        for i in range(self.latent_dim):
            binary_code[np.nonzero(X[:,i] < self.threshold[i]),i] = 0
            binary_code[np.nonzero(X[:,i] >= self.threshold[i]),i] = 1
        return binary_code.astype(int)
    def fit_transform(self, X):
        self.fit(X)
        return self.transform(X)
    
def get_similar(query, corpus,tipo="topK", K=100, ball=2):
    """
        Retrieve similar documents to the query document inside the corpus (source)
    """    
    query_similares = [] #indices
    for number, dato_hash in enumerate(query):
        hamming_distance = np.sum(dato_hash != corpus,axis=1) #distancia de hamming (# bits distintos)
        if tipo=="EM": #match exacto
            ball= 0
        
        if tipo=="ball" or tipo=="EM":
            K = np.sum(hamming_distance<=ball) #find K over ball radius
            
        #get topK
        ordenados = np.argsort(hamming_distance) #indices
        query_similares.append(ordenados[:K]) #get top-K
    return query_similares

def measure_metrics(labels_name, data_retrieved_query, labels_query, labels_source):
    """
        Measure precision at K and recall at K, where K is the len of the retrieval documents
    """
    #relevant document for query data
    count_labels = {label:np.sum([label in aux for aux in labels_source]) for label in labels_name} 
    
    precision = 0.
    recall =0.
    for similars, label in zip(data_retrieved_query, labels_query): #source de donde se extrajo info
        if len(similars) == 0: #no encontro similares:
            continue
        labels_retrieve = labels_source[similars] #labels of retrieved data
        
        if type(labels_retrieve[0]) == list or type(labels_retrieve[0]) == np.ndarray: #multiple classes
            tp = np.sum([len(set(label)& set(aux))>=1 for aux in labels_retrieve]) #al menos 1 clase en comun --quizas variar
            recall += tp/np.sum([count_labels[aux] for aux in label ]) #cuenta todos los label del dato
        else: #only one class
            tp = np.sum(labels_retrieve == label) #true positive
            recall += tp/count_labels[label]
        precision += tp/len(similars)
    
    return precision/len(labels_query), recall/len(labels_query)

def P_atk(labels_retrieved, label_query, K=1):
    """
        Measure precision at K
    """
    #if len(data_retrieved_query) == 0: #no encontro similares:
    #    print("no hay SIMILARES")
    #    return 0
    if len(labels_retrieved)>K:
        labels_retrieved = labels_retrieved[:K]

        
    if type(labels_retrieved[0]) == list or type(labels_retrieved[0]) == np.ndarray: #multiple classes
        tp = np.sum([len(set(label_query)& set(aux))>=1 for aux in labels_retrieved]) #al menos 1 clase en comun --quizas variar
    else: #only one class
        tp = np.sum(labels_retrieved == label_query) #true positive
    
    return tp/len(labels_retrieved) #or K

def M_P_atk(datas_similars, labels_query, labels_source, K=1):
    """
        Mean (overall the queries) precision at K
    """
    return np.mean([P_atk(labels_source[datas_similars[i]],labels_query[i],K=K) if len(datas_similars[i]) != 0 else 0.
                    for i,_ in enumerate(datas_similars)])

def measure_metrics_P(labels_name, data_retrieved_query, labels_data, labels_source):
    return M_P_atk(val_similares_val, labels_val, K=99999999) #to all the list

def AP_atk(data_retrieved_query, label_query, labels_source, K=0):
    """
        Average precision at K, average all the list precision until K.
    """
    if K == 0:
        K = len(data_retrieved_query)
    
    if len(data_retrieved_query)>K:
        data_retrieved_query = data_retrieved_query[:K]
    
    labels_retrieve = labels_source[data_retrieved_query] 
    
    score = []
    for i in range(K):
        if label_query in labels_retrieve[i]: #only if "i"-element is relevant 
            score.append( P_atk(labels_retrieve, label_query, K=i+1) )
            
    if len(score) ==0:
        return 0
    else:
        return np.mean(score)

def MAP_atk(datas_similars, labels_query, labels_source, K=0):
    """
        Mean (overall the queries) average precision at K
    """
    return np.mean([AP_atk(datas_similars[i], labels_query[i], labels_source, K=K) if len(datas_similars[i]) != 0 else 0.
                    for i,_ in enumerate(datas_similars)]) 


##valores unicos de hash? distribucion de casillas
def hash_analysis(hash_data):
    hash_string = []
    for valor in hash_data:
        hash_string.append(str(valor)[1:-1].replace(' ',''))
    valores_unicos = set(hash_string)
    count_hash = {valor: hash_string.count(valor) for valor in valores_unicos}
    return valores_unicos, count_hash

def compare_cells_plot(nb,train_hash1,train_hash2,test_hash1=[],test_hash2=[]):
    print("Entrenamiento----")
    print("Cantidad de datos a llenar la tabla hash: ",train_hash1.shape[0])

    valores_unicos, count_hash =  hash_analysis(train_hash1)
    print("Cantidad de memorias ocupadas hash1: ",len(valores_unicos))
    plt.figure(figsize=(14,4))
    plt.plot(sorted(list(count_hash.values()))[::-1],'bo-',label="Binary")
    
    valores_unicos, count_hash =  hash_analysis(train_hash2)
    print("Cantidad de memorias ocupadas hash2: ",len(valores_unicos))
    plt.plot(sorted(list(count_hash.values()))[::-1],'go-',label="Traditional")
    plt.legend()
    plt.show()
    
    if len(test_hash1) != 0:
        print("Pruebas-----")
        print("Cantidad de datos a llenar la tabla hash: ",test_hash1.shape[0])
        
        valores_unicos, count_hash =  hash_analysis(test_hash1)
        print("Cantidad de memorias ocupadas hash1: ",len(valores_unicos))
        plt.figure(figsize=(15,4))
        plt.plot(sorted(list(count_hash.values()))[::-1],'bo-',label="Binary")
        
        valores_unicos, count_hash =  hash_analysis(test_hash2)
        print("Cantidad de memorias ocupadas hash2: ",len(valores_unicos))
        plt.plot(sorted(list(count_hash.values()))[::-1],'go-',label="Traditional")
        plt.legend()
        plt.show()
        

from PIL import Image
def check_availability(folder_imgs, labels_aux):
    imgs_files = os.listdir(folder_imgs)

    mask_ = np.zeros((len(imgs_files)), dtype=bool) 
    for contador, (img_n, la) in enumerate(zip(imgs_files, labels_aux)):
        if contador%10000==0:
            gc.collect()
        
        if img_n in imgs_files and len(la)!=0: #si imagen fue descargada y tiene labels.
            imagen = Image.open(folder_imgs+img_n)
            aux = np.asarray(imagen)
            if len(aux.shape) == 3 and aux.shape[2] == 3:#si tiene 3 canals
                mask_[contador] = True
            
            imagen.close()
    return mask_

def load_imgs_mask(imgs_files, mask_used, size, dtype = 'float32'):
    N_used = np.sum(mask_used)
    X_t = np.zeros((N_used, size,size,3), dtype=dtype)
    real_i = 0
    for contador, foto_path in enumerate(imgs_files):
        if contador%10000==0:
            print("El contador de lectura va en: ",contador)
            gc.collect()

        if mask_used[contador]:
            #abrir imagen
            imagen = Image.open(foto_path)
            aux = imagen.resize((size,size),Image.ANTIALIAS)
            X_t[real_i] = np.asarray(aux, dtype=dtype)

            imagen.close()
            aux.close()
            del aux, imagen
            real_i +=1
    return X_t