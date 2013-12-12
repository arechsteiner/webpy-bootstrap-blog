import hashlib
from datetime import datetime

import peewee as pw
from playhouse.signals import Model, pre_save
from peewee import SqliteDatabase
import config
import operator

DoesNotExist = pw.DoesNotExist
SelectQuery = pw.SelectQuery


#we need these two lines or SQLite will complain about interthread access
db = SqliteDatabase('peewee.db',threadlocals=True)
db.connect()

def better_get(self, **kwargs):
    if kwargs:
        return self.filter(**kwargs).get()
    clone = self.paginate(1, 1)
    try:
        return clone.execute().next()
    except StopIteration:
        raise self.model_class.DoesNotExist(
            'instance matching query does not exist:\nSQL: %s\nPARAMS: %s' % (
                self.sql()))

pw.SelectQuery.get = better_get


class BaseModel(Model):
    created_at = pw.DateTimeField(default="now()",null=False)
    id = pw.PrimaryKeyField()
    
    class Meta:
        database = db

    def update_fields(self, **kwargs):
        for field, value in kwargs.items():
            setattr(self, field, value)
        return self.save()
    
class Credit(BaseModel):
    url = pw.CharField(max_length=4096,null=False)
    alt = pw.CharField(max_length=512,null=True)
    title = pw.CharField(max_length=1024,null=True)
    author = pw.CharField(max_length=1024,null=True)
    link = pw.CharField(max_length=4096,null=False)
    license = pw.CharField(max_length=1024,null=False)
    
    @staticmethod
    def get_all():
        return Credit.select()
    
    @staticmethod
    def by_id(id):
        u = None
        try:
            u=Credit.get(Credit.id == id)
        except: 
            return None
        return u

    
    
class User(BaseModel):
    name = pw.CharField(max_length=200, null=False)
    email = pw.CharField(max_length=200, null=False)
    crypted_password = pw.CharField(max_length=40, null=False)
    salt = pw.CharField(max_length=40, null=False)
    remember_token = pw.CharField(max_length=64, null=True)
    
    @staticmethod
    def create_user(name,email,password):
        try:
            #check if user already exists
            User.get(User.name == name)
        except User.DoesNotExist:
            #nope , create him
            #the @pre_save thingy below will auto salt and hash the password
            return User.create(name=name,email=email,password=password,created_at=datetime.now())
            
    @staticmethod
    def by_id(id):
        u = None
        try:
            u=User.get(User.id == id)
        except: 
            return None
        return u
    
    @staticmethod
    def by_name(name):
        u = None
        try:
            u=User.get(User.name == name)
        except: 
            return None
        return u
    
    def authenticate(self, password):
        return self.crypted_password == crypt_password(password,
                                                       self.salt)

    def __unicode__(self):
        return unicode(self.name)

class Post(BaseModel):
    title = pw.CharField(max_length=200, null=False)
    title_img = pw.CharField(max_length=1024,null=True)
    big_img = pw.CharField(max_length=1024,null=True)
    #comma separated list of "tags"
    tags = pw.TextField(null=True) 
    author = pw.ForeignKeyField(User)
    updated = pw.DateTimeField(null=True)
    category = pw.CharField(max_length=256,null=True)
    subcategory = pw.CharField(max_length=256,null=True)
    html = pw.TextField(null=False)
    favorite = pw.BooleanField(default=False)
    public = pw.BooleanField(default=True)
    
    
    @staticmethod
    def by_category(cat,subcat):
        posts = None
        if subcat == None:
            posts = Post.select().where(Post.category == cat).order_by(Post.created_at.desc())
        else:   
            posts = Post.select().where(Post.category == cat).where(Post.subcategory == subcat).order_by(Post.created_at.desc())
            
        return posts
    
    @staticmethod
    def by_tag(tag):
        search_str = "%s%s%s" % (config.db_wildcard,tag,config.db_wildcard)
        posts = Post.select().where(Post.tags % search_str).order_by(Post.created_at.desc())
        return posts
    
    @staticmethod
    #get the next amt posts afer date
    def get_next(date,amt=5):
        #get original post
        #op = Post.get(id = id)
        posts = Post.select().where(Post.created_at > date).order_by(Post.created_at.desc()).limit(amt)
        
        return posts
    
    @staticmethod
    def get_favs(amt=5):
        posts = Post.select().where(Post.favorite == True).order_by(Post.created_at.desc()).limit(amt)
        #print "Favorite posts:" + posts
        return posts
    @staticmethod
    def nth_most_recent(n):
        posts = Post.select().order_by(Post.created_at.desc()).limit(n)
        for item in posts:
            pass
        return item
    @staticmethod
    def recent_posts(n):
        return Post.select().order_by(Post.created_at.desc()).limit(n)
    
    @staticmethod
    def new(title,tags,author_id,html,img,bimg,cat=None,subcat=None,fav = False):
        #get user by id
        user = User.by_id(author_id)
        p = Post.create(title=title,tags=tags,author=user,html=html,
                        title_img=img,big_img=bimg,created_at=datetime.now(),favorite=fav,category=cat,subcategory=subcat)

    @staticmethod
    def by_id(id):
        p = None
        try:
            p=Post.get(Post.id==id)
        except: 
            return None
        return p
    
    @staticmethod
    def get_recent(num):
        return Post.select().order_by(Post.created_at.asc()).limit(num)
    
    #while this is here ,now we need to move it out to some type of static
    #place and simply update it every time there is a new post
    @staticmethod
    def all_tags():
        tag_map = {}
        tags = Post.select(Post.tags)
        for taglist in tags:
            for tag in taglist.tags.split(","):
                cur = tag_map.get(tag,0)
                tag_map[tag] = cur+1
        sorted_x = sorted(tag_map.iteritems(), key=operator.itemgetter(1),reverse=True)
        print sorted_x
        return sorted_x


class Comment(BaseModel):
    title = pw.CharField(max_length=512,default="Comment")
    author = pw.CharField(max_length=512,null=False)
    auth_url = pw.CharField(max_length=2048,null=True)
    post = pw.ForeignKeyField(Post,null=False)
    text = pw.TextField(max_length=16656,null=False)
    #meta-data
    parent = pw.ForeignKeyField('self',related_name='children',null=True)
    rank = pw.IntegerField(null=False,default=0)
    indent = pw.IntegerField(null=False,default=0)

    @staticmethod
    def get_comments(postid):
        count = Comment.select().where(Comment.post == postid).order_by(Comment.rank.asc()).count()
        return (count,Comment.select().where(Comment.post == postid).order_by(Comment.rank.asc()))

    @staticmethod
    def new(postid,parentid,title,author,text):
        #1 get parent
        rank = 0
        indent = 0
        lastcomment = None
        if parentid == -1:
            #just insert at the end, 
            c = Comment.select().where(Comment.post == postid).order_by(Comment.rank.desc()).limit(1).execute()
            for lastcomment in c:
                pass
            if lastcomment != None:
                rank = lastcomment.rank+1
            else:
                #this must be the first record!?!?
                print "Inserting first record!"
            return Comment.create(title=title,author=author,post=postid,text=text,rank=rank,indent=indent,created_at=datetime.now())
        else:
            parent=Comment.get(Comment.id==parentid)
            #prep for insertion 
            #update all old posts whose rank are greater than parent
            Comment.update(rank=Comment.rank + 1).where(Comment.rank > parent.rank).execute()
            #insert at rank of parent + 1 aka where we just made room
            new_comment = Comment.create(title=title,author=author,post=postid,text=text,rank=parent.rank+1,indent=parent.indent+1,created_at=datetime.now())

            return new_comment
    

def print_dates(d):
    return d.strftime("%B %d %Y ")        
        
    
def create_salt(email):
    return hashlib.md5("--%s--%s--" % (datetime.now(),
                                       email)).hexdigest()


def crypt_password(password, salt):
    return hashlib.md5("--%s--%s--" % (salt, password)).hexdigest()


# Fix reloading during development :-/
try:
    pre_save.disconnect(name='crypt_password_before_save')
except:
    pass


#update comment display order when posting
#see :http://evolt.org/node/4047/
#@pre_save(sender=Comment)
#def update_ranks(model_class,instance,created):
#    if not instance.rank:
#        return
#    if created == True:
#        Comment.update(rank=Comment.rank + 1).where(Comment.rank > instance.rank)
#    else:
#        print "in update_rank, but created was false"

@pre_save(sender=User)
def crypt_password_before_save(model_class, instance, created):
    if not instance.password:
        return
    if not instance.salt:
        instance.salt = create_salt(instance.email)
    instance.crypted_password = crypt_password(instance.password,
                                               instance.salt)
