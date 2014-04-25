import ckan.lib.helpers as h
from ckan.plugins import SingletonPlugin, implements, IDomainObjectModification,  IConfigurable, toolkit
from ckan.lib.dictization.model_dictize import resource_dictize
from ckan.logic import get_action
from ckan.lib.celery_app import celery
from vector import Shapefile
from pylons import config
from ckan.model.types import make_uuid
from ckan import model
import json


package_name=''
class VectorStorer(SingletonPlugin):
    resource_changed=False
    dataset_new=False
    package_name=''
    """
    Registers to be notified whenever CKAN resources are created or their URLs change,
    and will create a new ckanext.archiver celery task to archive the resource.
    """
    implements(IConfigurable, inherit=True)
    implements(IDomainObjectModification, inherit=True)
    
    def configure(self, config):
        self.config=config
        
	
    def notify(self, entity, operation=None):
	
	if isinstance(entity, model.Package) and operation== model.DomainObjectOperation.new:
	    self.package_name=entity.name
	    
        if not isinstance(entity, model.Resource):
            return
	 
	if entity.format.lower()=='zip':
	    
	    user = get_action('get_site_user')({'model': model,
                                            'ignore_auth': True,
                                            'defer_commit': True}, {})
	  
	    #package_name= get_action('package_show_rest')({'model': model,
                                            #'ignore_auth': True,
                                            #'defer_commit': True}, {'id':str(entity.resource_group_id)})
	    
	    self._create_vector_storer_task(entity)
	    entity.format="shapefile"
	else:
	    return
	
    def _get_site_url(self):
        try:
            return h.url_for_static('/', qualified=True)
        except AttributeError:
            return config.get('ckan.site_url', '')

    def _create_vector_storer_task(self, resource):
        user = get_action('get_site_user')({'model': model,
                                            'ignore_auth': True,
                                            'defer_commit': True}, {})

        context = json.dumps({
	     'package_name': self.package_name,
            'site_url': self._get_site_url(),
            'apikey': user.get('apikey'),
            'site_user_apikey': user.get('apikey'),
            'user': user.get('name'),
            'db_params':self.config['ckan.datastore.write_url']
            
        })
	geoserver_context = json.dumps({
	    'geoserver_public_url': self.config['ckanext-vectorstorer.geoserver_public_url'],
            'geoserver_local_url': self.config['ckanext-vectorstorer.geoserver_local_url'],
            'geoserver_workspace': self.config['ckanext-vectorstorer.geoserver_workspace'],
            'geoserver_admin': self.config['ckanext-vectorstorer.geoserver_admin'],
            'geoserver_password': self.config['ckanext-vectorstorer.geoserver_password']
        })
        data = json.dumps(resource_dictize(resource, {'model': model}))

        task_id = make_uuid()
     
	
        
        celery.send_task("vectorstorer.upload",
                         args=[geoserver_context,context, data],
                         task_id=task_id)