from pyVim import connect 
from pyVmomi import vim
import argparse
import sys
import atexit
import json
import argparse

class set_params(object):
    pass

def connect_vcenter(vcname, vcuser, vcpass):
    """
    Takes vcentername, vc user and vc password.
    returns instance of the connection.
    A new instance of object returned by the fucntion is to required to be created.
    e.g : -
    service_instance = connect_vcenter("avcenter001z.test.local", "vcuser", "vcpass")
    content= service_instance.content
    """
    #s=ssl.SSLContext(ssl.PROTOCOL_TLSv1)
    #s.verify_mode=ssl.CERT_NONE    
    #service_instance= connect.SmartConnect(host=vcname, user=vcuser, pwd=vcpass ,sslContext=s)

    service_instance= connect.SmartConnectNoSSL(host=vcname, user=vcuser, pwd=vcpass)
    return service_instance

def get_all_objs(content, vimtype):
    """
    Talkes 2 arguments. 
    1. content from vservice service instance
    2. vimtype.
    e.g : - 
    datacenters = get_all_objs(content,[vim.Datacenter])
    """
    obj = {}
    container = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
    for managed_object_ref in container.view:
        obj.update({managed_object_ref: managed_object_ref.name})       
    return obj

def alarm_spec(alarm_parameters):
    
    alarm_spec = vim.alarm.AlarmSpec()
    alarm_spec.action = create_alarmtriggeraction(tolist=alarm_parameters.toList,repeats=alarm_parameters.repeat)
    alarm_spec.actionFrequency = alarm_parameters.actionfrequency
    alarm_spec.description = alarm_parameters.description
    alarm_spec.expression = create_metricalarmexpression(alarm_values=alarm_parameters.alarm_values)
    alarm_spec.enabled = alarm_parameters.enabled
    alarm_spec.name = alarm_parameters.name
    alarm_spec.setting = vim.alarm.AlarmSetting(reportingFrequency=alarm_parameters.reportingfrequency,
                                                    toleranceRange=alarm_parameters.tolerancerange)

    return alarm_spec

def create_alarmtriggeraction(tolist,repeats):
    


    alrmaction = vim.alarm.GroupAlarmAction()
    #alrmaction.action = [vim.alarm.AlarmTriggeringAction()]
    
    action = vim.alarm.AlarmTriggeringAction()
    action.green2yellow = False
    action.yellow2red = True
    action.red2yellow = False
    action.yellow2green = False
    action.action = vim.action.SendEmailAction(
                                                    toList = tolist,
                                                    ccList = '',
                                                    subject = '[vCenter Alarm] {alarmName} : {targetName} : {newStatus}',
                                                    body =  '{triggeringSummary}: {eventDescription}'
                                                )
    action.transitionSpecs = [vim.alarm.AlarmTriggeringAction.TransitionSpec(startState = 'yellow',finalState = 'red',repeats = repeats)]
    #action =vim.alarm.AlarmAction()
    alrmaction.action = [action]
    return alrmaction

def create_metricalarmexpression(alarm_values):
    alarmexpression = vim.alarm.OrAlarmExpression()     
    if 'datastore' in alarm_values.alarmtype :
        expression = vim.alarm.MetricAlarmExpression(
                                                            operator = vim.alarm.MetricAlarmExpression.MetricOperator('isAbove'),
                                                            type = vim.Datastore,
                                                            metric = vim.PerformanceManager.MetricId(
                                                                                                        counterId = alarm_values.counterid,
                                                                                                        instance = ''
                                                                                                    ),
                                                            red=alarm_values.redthreshold*100
                                                        ) 
    elif ('esxi-' in alarm_values.alarmtype) or ('host' in alarm_values.alarmtype):

        expression = vim.alarm.StateAlarmExpression(
            operator = 'isEqual',
            type = vim.HostSystem,
            statePath = 'runtime.connectionState',
            red = 'notResponding' 
        ) if 'riaas_host_connection' in alarm_values.alarmtype.lower() else vim.alarm.MetricAlarmExpression(
                                                                                operator = vim.alarm.MetricAlarmExpression.MetricOperator('isAbove'),
                                                                                type = vim.HostSystem,
                                                                                metric = vim.PerformanceManager.MetricId(
                                                                                                                            counterId = alarm_values.counterid,
                                                                                                                            instance = ''
                                                                                                                        ),
                                                                                red=alarm_values.redthreshold*100,
                                                                                yellow = alarm_values.yellowthreshold*100,
                                                                                yellowInterval = alarm_values.yellowinterval,
                                                                                redInterval = alarm_values.interval
                                                                            )   
    alarmexpression.expression = [expression]
    #print(f"create_metricalarmexpression  : {alarmexpression}")
    return alarmexpression

def set_alarm(content,alarmtype,entity,alarm_info):
    """Function to set alarm on the object """
    print(f"[WARN] Missing alarm type {alarmtype} on {entity.name}")
      
    if 'datastore_provisioned' in alarmtype and 'full' in entity.name.lower(): #skip setting of provisioned space on full cluster
        print(f"[INFO] Skip setting provisioned alarm on datastore full cluster {entity.name}")
        return
    
    print(f"[INFO] Settting alarm type {alarmtype} on {entity.name }")

    def set_alarm_parameters(exception_item):

        if 'ALL' != exception_item:
            #If name found under exception
            alarm_parameters.repeat = True if 'ACTIONFREQUENCY' in alarm_info[alarmtype]['USAGE']['EXCEPTION'][exception_item] else False
            alarm_parameters.actionfrequency = alarm_info[alarmtype]['USAGE']['EXCEPTION'][exception_item]["ACTIONFREQUENCY"] if 'ACTIONFREQUENCY' in alarm_info[alarmtype]['USAGE']['EXCEPTION'][exception_item] else None
            alarm_values.redthreshold = alarm_info[alarmtype]["USAGE"]['EXCEPTION'][exception_item]["ALARMREDTHRESHOLD"] if "ALARMREDTHRESHOLD" in alarm_info[alarmtype]["USAGE"]['EXCEPTION'][exception_item] else None
            alarm_values.interval = alarm_info[alarmtype]["USAGE"]['EXCEPTION'][exception_item]["ALARMINTERVAL"] if "ALARMINTERVAL" in alarm_info[alarmtype]["USAGE"]['EXCEPTION'][exception_item] else None

        else :
            alarm_parameters.repeat = True if 'ACTIONFREQUENCY' in  alarm_info[alarmtype]['USAGE'][exception_item] else False       
            alarm_parameters.actionfrequency = alarm_info[alarmtype]['USAGE'][exception_item]["ACTIONFREQUENCY"] if 'ACTIONFREQUENCY' in alarm_info[alarmtype]['USAGE'][exception_item] else None
            alarm_values.redthreshold = alarm_info[alarmtype]["USAGE"][exception_item]["ALARMREDTHRESHOLD"] if "ALARMREDTHRESHOLD" in alarm_info[alarmtype]["USAGE"][exception_item] else None            
            alarm_values.interval = alarm_info[alarmtype]["USAGE"][exception_item]["ALARMINTERVAL"] if "ALARMINTERVAL" in alarm_info[alarmtype]["USAGE"][exception_item] else None

        alarm_parameters.reportingfrequency = 0
        alarm_parameters.tolerancerange = 0
        alarm_parameters.toList = alarm_info[alarmtype]['USAGE']['EMAIL']        
        alarm_values.counterid = [x.key for x in content.perfManager.QueryPerfCounter(counterId=counterids) if x.nameInfo.label == counterid[alarmtype] ][0] if 'connection' not  in alarmtype  else None       
        alarm_values.alarmtype = alarmtype

    perfMetricIDs = content.perfManager.QueryAvailablePerfMetric(entity)
    counterids = [x.counterId for x in perfMetricIDs ] 
    #Usage  -> cpu
    #Host consumed %   -> memory
    #"Space potentially used"
    #'Space actually used'

    counterid = {} #counterID are different for vCenter version 6.5 and 7.0
    counterid['datastore_usage'] = 'Space actually used' #241 if content.about.version == '6.5.0' else 281
    counterid['datastore_provisioned'] = 'Space potentially used'  #242 if content.about.version == '6.5.0' else 282
    counterid['riaas_host_cpu_usage'] = 'Usage' #2
    counterid['riaas_host_mem_usage'] = 'Host consumed %'  #24  
    #print(f"counterids {counterid[alarmtype]}     ")
    #print(f" TEST { [x.key for x in content.perfManager.QueryPerfCounter(counterId=counterids) if x.nameInfo.label == ]}")  #if 'connection' not  in alarmtype  else None       }")

    alarm_parameters = set_params()
    alarm_parameters.enabled = True
    alarm_values = set_params()
    
    alarm_parameters.name = f"RIaaS_{alarmtype.upper()}_HIGH_{entity.name}"
    alarm_parameters.description = f"Alarm definitions to monitor { alarmtype.replace('_',' ').replace('riaas','')}" 
    alarm_values.yellowthreshold = 75 if 'connection' not  in alarmtype  else None #percentage
    alarm_values.yellowinterval =  300  if 'connection' not  in alarmtype  else None #Seconds

    if alarm_info[alarmtype]['USAGE']['EXCEPTION'] != {}:
        print(f"[INFO] Checking exception list")
        for key  in alarm_info[alarmtype]['USAGE']['EXCEPTION']:
            print(f"[INFO] Checking for key {key}")
            if key.lower() in entity.name.lower():
                print(f"[INFO] Cluster {entity.name} is under exception settings ")
                set_alarm_parameters(exception_item=key)
            else:
                print(f"[INFO] {entity.name} not in exception list")
                set_alarm_parameters(exception_item="ALL")
    if alarm_info[alarmtype]['USAGE']['EXCEPTION'] == {}:
        set_alarm_parameters(exception_item="ALL")

    alarm_parameters.alarm_values = alarm_values
    spec = alarm_spec(alarm_parameters)
    content.alarmManager.CreateAlarm(entity=entity,spec=spec)

def check_alarm(content,entity,alarm_info):
    """Check if required alarm exists on the host/datastore cluster"""

    alarm_defs = content.alarmManager.GetAlarm(entity)
    alarm_list = alarm_info["alarmtype"]    
    print(f"[INFO] Alarm {alarm_list} exits on {entity.name}") if any(alarm_list in x.info.name.lower() for x in alarm_defs) else  set_alarm(content=content,alarmtype=alarm_list,entity=entity,alarm_info=alarm_info["data"])

def itterate_objects(content,object_list,data,flag,skip_objects=None):
    """check objects"""
  
    for item in object_list:

        if flag == "datastore":    
            if not any(x.lower() in item.name.lower() for x in skip_objects):            
                for datastore_alarm_type in ['datastore_usage','datastore_provisioned']:
                    check_alarm(content=content,entity=item,alarm_info={"alarmtype":datastore_alarm_type,"data":data["datastore"]})
        
        if flag == 'host':
            for host_alarm_type in ['riaas_host_cpu_usage','riaas_host_mem_usage','riaas_host_connection']:
                skip_objects = data['skip_compute_clusters'] if host_alarm_type != "riaas_host_connection" else data['skip_connection_cluster']
                if not any(x.lower() in item.name.lower() for x in skip_objects): 
                    check_alarm(content=content,entity=item,alarm_info={"alarmtype":host_alarm_type,"data":data["esxi"]})

def err_msg(error,si):
    """Error handler function"""
    print(f"[ERROR] Error occured while execution : {error}") if error != None else None
    print(f"[INFO] Disconnecting from vCenter server {connect.Disconnect(si=si)} ") if si != None else print(f"[ERROR] Not connected to vcenter. Check argument values") 
    print(f"[ERROR] Argument values empty") if len(sys.argv)==1 else None                
    print("[INFO] Terminating script due to error")
    sys.exit(1)

def get_args():
    """Get arguments"""
    parser = argparse.ArgumentParser(description='vCenter server details')
    parser.add_argument("-u", '--vcusername', required=True, help='vc username')
    parser.add_argument("-p", '--vcpassword', required=True, help='vc password')
    parser.add_argument("-v", '--vcentername', required=True, help='name of the vc server')

    args = parser.parse_args()
    return args

def main():
    """Connect vcenter server and check if alarms are set."""
    try:
        service_instance = None
        args = get_args()
        print(f"[INFO] Connecting to vCenter server {args.vcentername}")
        service_instance = connect_vcenter(vcname=args.vcentername,vcuser=args.vcusername,vcpass=args.vcpassword) #connect to vcenter server
        content = service_instance.content
        print(f"[INFO] vcenter version : {content.about.version}")
        host_clusters = get_all_objs(content=content,vimtype=[vim.ComputeResource]) #Retrive host clusters
        datastore_clusters = get_all_objs(content=content,vimtype=[vim.StoragePod]) #Retrive datastore clusters
        
        #Read JSON data
        with open(file='VC_Alert/vcenter-alarm-check-set-rules.json',mode='r') as file_object:
            data = json.load(file_object)
        #Check for datastore
        print(f"[INFO] Checking datastore cluster objects")
        itterate_objects(content=content,object_list=datastore_clusters,skip_objects=data['skip_datastores'],data=data,flag='datastore')
        print(f"\n[INFO] Checking host cluster objects")
        #Check for host clusters
        itterate_objects(content=content,object_list=host_clusters,data=data,flag='host')    
   
    except Exception as e:
        err_msg(error=e,si=service_instance)

    print(f"[INFO] Disconnecting form the vCenter server")
    connect.Disconnect(si=service_instance)

if __name__ == "__main__":
    sys.exit(main())
