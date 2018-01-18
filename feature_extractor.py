# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import pandas as pd
import numpy as np
 
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import BaggingClassifier
import string
import unicodedata
import re
import nltk
from nltk import word_tokenize
from nltk.corpus import stopwords
from .constants import *

#from nltk.sentiment.vader import SentimentIntensityAnalyzer
#from nltk.stem.wordnet import WordNetLemmatizer
 
 
def bin_(x):
    """ Binarize the target to predict """
    return int(x>=3)


def strip_accents_unicode(s):
    """ Deals with string encoding issues """
    try:
        s = unicode(s, 'utf-8')
    except:  # unicode is a default on python 3
        pass
    s = unicodedata.normalize('NFD', s)
    s = s.encode('ascii', 'ignore')
    s = s.decode("utf-8")
    return str(s)


def process(s):
    """ Simple text processing """
    punctuation = set(string.punctuation)
    punctuation.update(["``", "`", "..."])
    def clean_str(sentence):
        #verbs_stemmer = WordNetLemmatizer()
        return list((filter(lambda x: x.lower() not in punctuation and x.lower() not in english_stopwords,
                    [t.lower() for t in word_tokenize(sentence)
                     if t.isalpha()]))) ## verbs_stemmer.lemmatize(t.lower(),'v')
    s_ = strip_accents_unicode(s)
    s_ = s_.replace("I'm ", "I am ")
    s_ = s_.replace("It's ", "It is ")
    s_ = s_.replace("it's ", "it is ")
    s_ = s_.replace("he's ", "he is ")
    s_ = s_.replace("she's ", "she is ")
    s_ = s_.replace("He's ", "He is ")
    s_ = s_.replace("She's ", "She is ")
    s_ = s_.replace("'ll ", " will ")
    s_ = s_.replace("can't", "can not")
    s_ = s_.replace("won't", "will not")
    s_ = s_.replace("n't ", " not ")
    s_ = s_.replace("'re ", " are ")
    s_ = s_.replace("-", ' ')
 
    return " ".join(clean_str(s_))


def count_numbers(s):
    """ Counts all numbers that occur in the statement, excepting dates """
    try:
        return len([e for e in re.findall(r'[0-9]*[.,]*[0-9]+', s) if ((len(e)!=4) or (len(e)==4 and int(e[0]) not in [1,2]))])
    except:
        return 0

def count_the(s):
    """ Counts undedfined articles occurences in the statement """
    return len([e for e in word_tokenize(s) if e.lower() in ['the', 'a', 'an']])


class MetaVectorizer:
    """ A class to vectorize the meta information that comes with the statement.
        The strategy is to calculate the ratios fake_statement/total_statements
        for a given subject, editor, journalist, ...
        The calculation is done over the training data and some Bayesian Smoothing
        is used to re estimate the ratios more fairly.
    """
    def __init__(self, dict_parameters):
        self.dict_parameters = dict_parameters
        pass
    

    def make_source(self, X_df, y):
        sources = list(X_df.source.unique())
        df_bin = pd.get_dummies(X_df.source)
        df_bin['label'] = [bin_(s) for s in y]
        df_false = df_bin[df_bin.label == 0].sum()
        df_true = df_bin[df_bin.label == 1].sum()
        false_source = pd.DataFrame([(f, df_false[f], df_true[f] + df_false[f], df_false[f] / (
            df_false[f] + df_true[f])) for f in sources], columns=['source', 'n_false', 'n_total', 'false_ind'])
        false_source['false_ind_smoothed'] = (
            false_source['n_false'] + self.dict_parameters['ALPHA_SOURCE']) / (false_source['n_total'] + self.dict_parameters['ALPHA_SOURCE'] + self.dict_parameters['BETA_SOURCE'])
        return false_source


    def make_journalist(self, X_df, y):
        df_bin = pd.DataFrame()
        df_bin['truth'] = y
        df_bin['researched_by'] = X_df.researched_by.astype(
            str).apply(lambda s: s.split(', '))
        journalist_counts = []
        for ix, e in enumerate(df_bin['researched_by']):
            try:
                for f in e:
                    journalist_counts.append((f, df_bin.loc[ix, 'truth']))
            except:
                journalist_counts.append(('nan', df_bin.loc[ix, 'truth']))
        df_bin = pd.DataFrame(journalist_counts, columns=[
                              'researched_by', 'truth'])
        label = df_bin['truth'].apply(lambda s: bin_(s))
        df_bin = pd.get_dummies(df_bin.researched_by)
        if 'nan' in df_bin.columns:
            del df_bin['nan']
        journalists = list(df_bin.columns)
        df_bin['label'] = label
        df_false = df_bin[df_bin.label == 0].sum()
        df_true = df_bin[df_bin.label == 1].sum()
        false_journalist = pd.DataFrame([(f, df_false[f], df_true[f] + df_false[f], df_false[f] / (df_false[f] + df_true[f]))
                                         for f in journalists], columns=['journalist', 'n_false', 'n_total', 'false_ind'])

        false_journalist['false_ind_smoothed'] = (false_journalist['n_false'] + self.dict_parameters['ALPHA_JOURNALIST']) / (
            false_journalist['n_total'] + self.dict_parameters['ALPHA_JOURNALIST'] + self.dict_parameters['BETA_JOURNALIST'])
        return false_journalist


    def make_editor(self, X_df, y):
        df_bin = pd.DataFrame()
        df_bin['truth'] = y
        df_bin['edited_by'] = X_df.edited_by.astype(
            str).apply(lambda s: s.split(', '))
        editor_counts = []
        for ix, e in enumerate(df_bin['edited_by']):
            try:
                for f in e:
                    editor_counts.append((f, df_bin.loc[ix, 'truth']))
            except:
                editor_counts.append(('nan', df_bin.loc[ix, 'truth']))
        df_bin = pd.DataFrame(editor_counts, columns=['edited_by', 'truth'])
        label = df_bin['truth'].apply(lambda s: bin_(s))
        df_bin = pd.get_dummies(df_bin.edited_by)
        if 'nan' in df_bin.columns:
            del df_bin['nan']
        editors = list(df_bin.columns)
        df_bin['label'] = label

        df_false = df_bin[df_bin.label == 0].sum()
        df_true = df_bin[df_bin.label == 1].sum()
        false_editor = pd.DataFrame([(f, df_false[f], df_true[f] + df_false[f], df_false[f] / (
            df_false[f] + df_true[f])) for f in editors], columns=['editor', 'n_false', 'n_total', 'false_ind'])
        false_editor['false_ind_smoothed'] = (
            false_editor['n_false'] + self.dict_parameters['ALPHA_EDITOR']) / (false_editor['n_total'] + self.dict_parameters['ALPHA_EDITOR'] + self.dict_parameters['BETA_EDITOR'])
        return false_editor


    def make_job(self, X_df, y):
        Xjob = X_df.job.fillna('None')
        jobs = list(Xjob.unique())
        jobs.remove('None')
        df_bin = pd.get_dummies(Xjob)
        if 'None' in df_bin.columns:
            del df_bin['None']
        df_bin['label'] = [bin_(s) for s in y]
        df_false = df_bin[df_bin.label == 0].sum()
        df_true = df_bin[df_bin.label == 1].sum()
        false_job = pd.DataFrame([(f, df_false[f], df_true[f] + df_false[f], df_false[f] / (
            df_false[f] + df_true[f])) for f in jobs], columns=['job', 'n_false', 'n_total', 'false_ind'])
        false_job['false_ind_smoothed'] = (
            false_job['n_false'] + self.dict_parameters['ALPHA_JOB']) / (false_job['n_total'] + self.dict_parameters['ALPHA_JOB'] + self.dict_parameters['BETA_JOB'])
        return false_job


    def make_subject(self, X_df, y):
        df_bin = pd.DataFrame()
        df_bin['truth'] = y
        df_bin['subjects'] = X_df.subjects.astype(str).apply(
            lambda s: re.findall(r'[A-Za-z0-9]+\'* *[A-Za-z0-9]+ *[A-Za-z0-9]+', str(s)))
        subject_counts = []
        for ix, e in enumerate(df_bin['subjects']):
            try:
                for f in e:
                    subject_counts.append((f, df_bin.loc[ix, 'truth']))
            except:
                subject_counts.append(('nan', df_bin.loc[ix, 'truth']))
        df_bin = pd.DataFrame(subject_counts, columns=['subjects', 'truth'])
        label = df_bin['truth'].apply(lambda s: bin_(s))
        df_bin = pd.get_dummies(df_bin.subjects)
        subjects = list(df_bin.columns)
        df_bin['label'] = label
        df_false = df_bin[df_bin.label == 0].sum()
        df_true = df_bin[df_bin.label == 1].sum()
        false_subject = pd.DataFrame([(f, df_false[f], df_true[f] + df_false[f], df_false[f] / (
            df_false[f] + df_true[f])) for f in subjects], columns=['subject', 'n_false', 'n_total', 'false_ind'])
        false_subject['false_ind_smoothed'] = (false_subject['n_false'] + self.dict_parameters['ALPHA_SUBJECT']) / (
            false_subject['n_total'] + self.dict_parameters['ALPHA_SUBJECT'] + self.dict_parameters['BETA_SUBJECT'])
        return false_subject


    def make_state(self, X_df, y):
        Xstate = X_df.state.fillna('None')
        states = list(Xstate.unique())
        states.remove('None')
        df_bin = pd.get_dummies(Xstate)
        if 'None' in df_bin.columns:
            del df_bin['None']
        df_bin['label'] = [bin_(s) for s in y]
        df_false = df_bin[df_bin.label == 0].sum()
        df_true = df_bin[df_bin.label == 1].sum()
        false_state = pd.DataFrame([(f, df_false[f], df_true[f] + df_false[f], df_false[f] / (
            df_false[f] + df_true[f])) for f in states], columns=['state', 'n_false', 'n_total', 'false_ind'])
        false_state['false_ind_smoothed'] = (
            false_state['n_false'] + self.dict_parameters['ALPHA_STATE']) / (false_state['n_total'] + self.dict_parameters['ALPHA_STATE'] + self.dict_parameters['BETA_STATE'])
        return false_state


    def score_journalist(s, false_journalist):
        try:
            return false_journalist.loc[false_journalist.journalist.isin(str(s).split(', ')), 'false_ind_smoothed'].mean()
        except:
            return np.nan
        
    def score_editor(s, false_editor):
        try:
            return false_editor.loc[false_editor.editor.isin(str(s).split(', ')), 'false_ind_smoothed'].mean()
        except:
            return np.nan
        
    def score_job(s, false_job):
        try:
            return float(false_job.loc[false_job['job']==s, 'false_ind_smoothed'])
        except:
            return np.nan
        
    def score_subject(s, false_subject):
        try:
            return false_subject.loc[false_subject.subject.isin( \
                            re.findall(r'[A-Za-z0-9]+\'* *[A-Za-z0-9]+ *[A-Za-z0-9]+',str(s))), 'false_ind_smoothed'].mean()
        except:
            return np.nan

    def score_state(s, false_state):
        try:
            return float(false_state.loc[false_state['state']==s, 'false_ind_smoothed'])
        except:
            return np.nan
        
    def score_source(s, false_source):
        try:
            return float(false_source.loc[false_source['source']==s,'false_ind_smoothed'])
        except:
            return np.nan
        
        
    def fit(self, X_df, y):
        self.false_source = make_source(X_df, y)
        self.false_journalist = make_journalist(X_df, y)
        self.false_editor = make_editor(X_df, y)
        self.false_job = make_job(X_df, y)
        self.false_subject = make_subject(X_df, y)
        self.false_state = make_state(X_df, y)
        pass
    
    
    def fit_transform(self, X_df, y):
        self.fit(X_df, y)
        return self.transform(X_df)
    
    
    def transform(self, X_df):
        _X_df = X_df.copy()
        _X_df['journalist_likes_truth'] = _X_df['researched_by'].apply(lambda s : 1-score_journalist(s, self.false_journalist))
        _X_df['editor_likes_truth'] = _X_df['edited_by'].apply(lambda s : 1-score_editor(s, self.false_editor))
        _X_df['job_prone_truth'] = _X_df['job'].apply(lambda s : 1-score_job(s, self.false_job))
        _X_df['subject_prone_truth'] = _X_df['subjects'].apply(lambda s : 1-score_subject(s, self.false_subject))
        _X_df['state_prone_truth'] = _X_df['state'].apply(lambda s : 1-score_state(s, self.false_state))
        _X_df['source_reliable'] = _X_df['source'].apply(lambda s : 1-score_source(s, self.false_source))      
        _X_df = X_df.loc[:, meta_features]
        for f in X_df_.columns:
            X_df_[f] = X_df_[f].fillna(value= X_df_[f].median())
        return X_df_
 
 
class FeatureExtractor():
    """ Extract features : TFIDF on words and TFIDF on POS-taggs are embedded with a Bagged Logistic Regression
        and mixed with meta features and a few other variables made from the statements.
    """
 
    def __init__(self):
        self.clf_bagged = BaggingClassifier(LogisticRegression(C= 5.), n_estimators = 300, max_features=0.8, bootstrap_features =True) ## 600
        self.vectorizer_text = TfidfVectorizer(ngram_range= (1,2), min_df=40) #50
        self.vectorizer_pos = TfidfVectorizer(ngram_range=(1,2), min_df=15) #20
        self.vectorizer_meta = MetaVectorizer(dict_parameters = BAYESIAN_PARAMETERS)
        pass
    
    def fit(self, X_df, y):
        self.vectorizer_meta.fit(X_df, y)
        
        tfidf_text = self.vectorizer_text.fit_transform(X_df.statement.apply(lambda s: process(s)))
        tfidf_pos = self.vectorizer_pos.fit_transform(X_df.statement.apply(lambda s: " ".join(list(zip(*nltk.pos_tag(word_tokenize(strip_accents_unicode(s)))))[1])))
        self.clf_bagged.fit(np.concatenate([tfidf_text.toarray(), tfidf_pos.toarray()], axis = 1), (y>2).astype(int))
        
        return self
 
    def fit_transform(self, X_df, y):
        self.fit(X_df, y)
        return self.transform(X_df)
 
    def transform(self, X_df):
        tfidf_text = self.vectorizer_text.transform(X_df.statement.apply(lambda s: process(s)))
        tfidf_pos = self.vectorizer_pos.transform(X_df.statement.apply(lambda s: " ".join(list(zip(*nltk.pos_tag(word_tokenize(strip_accents_unicode(s)))))[1])))
        dense_tfidf = self.clf_bagged.predict_proba(np.concatenate([tfidf_text.toarray(), tfidf_pos.toarray()], axis=1)) #[:,1].reshape(-1,1)

        df_train_meta = self.vectorizer_meta.transform(X_df)
        df_train_meta['n_fig']  = X_df.statement.apply(lambda s : count_numbers(strip_accents_unicode(s)))
        df_train_meta['n_fig'] = (df_train_meta['n_fig'] - df_train_meta['n_fig'].min()) / (df_train_meta['n_fig'].max() - df_train_meta['n_fig'].min())
        
        df_train_meta['n_the'] = X_df.statement.apply(lambda s : count_the(strip_accents_unicode(s)))
        df_train_meta['n_the'] = (df_train_meta['n_the'] - df_train_meta['n_the'].min()) / (df_train_meta['n_the'].max() - df_train_meta['n_the'].min())
 
        df_train_meta['is_obama'] = X_df.source.apply(lambda s : int(strip_accents_unicode(s)=='Barack Obama'))
        df_train_meta['is_clinton'] = X_df.source.apply(lambda s : int(strip_accents_unicode(s)=='Bill Clinton'))
        df_train_meta['is_brown'] = X_df.source.apply(lambda s : int(strip_accents_unicode(s)=='Sherrod Brown'))
        df_train_meta['is_portman'] = X_df.source.apply(lambda s : int(strip_accents_unicode(s)=="Rob Portman"))
        df_train_meta['is_kaine'] = X_df.source.apply(lambda s : int(strip_accents_unicode(s)=="Tim Kaine"))
        df_train_meta['is_kucinich'] = X_df.source.apply(lambda s : int(strip_accents_unicode(s)=="Dennis Kucinich"))
        df_train_meta['is_nelson'] = X_df.source.apply(lambda s : int(strip_accents_unicode(s)=="Bill Nelson"))
        df_train_meta['is_mail'] = X_df.source.apply(lambda s : int(strip_accents_unicode(s)=="Chain email"))
        df_train_meta['is_bloggers'] = X_df.source.apply(lambda s : int(strip_accents_unicode(s)=="Bloggers"))
        df_train_meta['is_dccc'] = X_df.source.apply(lambda s: int(strip_accents_unicode(s)=="Democratic Congressional Campaign Committee"))
        
        #clf = SentimentIntensityAnalyzer()
        #df_train_meta['polarity'] = X_df.statement.apply(lambda s : np.floor(np.abs(clf.polarity_scores(s)['compound'])/0.2)*0.2)
        
        return np.concatenate([dense_tfidf, df_train_meta], axis=1)