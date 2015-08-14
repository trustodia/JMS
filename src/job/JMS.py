from job.models import *

from utilities.io.shell import UserProcess
from utilities.io.filesystem import *
from utilities.security.cryptography import PubPvtKey

import objects

from django.conf import settings
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from django.http import Http404

import xml.etree.ElementTree as ET
import subprocess, os, pexpect,sys, pxssh, socket, requests, base64 #, pylibmc
from datetime import datetime
from shutil import copyfile  
from lxml import objectify

class JMS:
    
    def __init__(self, user=None):
        self.base_dir = settings.JMS_SETTINGS["JMS_shared_directory"]
        self.users_dir = "%s/%s" % (self.base_dir, "users/")       
        self.user = user
        


    def RunUserProcess(self, cmd, expect="prompt"):
        payload = "%s\n%s\n%s" % (self.user.filemanagersettings.ServerPass, cmd, expect)
        r = requests.post("http://%s/impersonate" % settings.IMPERSONATOR_URL, data=payload)
        return r.text
        
        
    def CreateFile(self, path, content):
        File.print_to_file(path, content, 'w', 0775)
    
    
    
    def GetWorkflow(self, WorkflowID):
        try:
            return Workflow.objects.get(pk=WorkflowID)
        except Exception, e:
            raise Http404
    
    
    
    def GetWorkflows(self):
        return Workflow.objects.raw("SELECT * FROM Workflows w INNER JOIN UserWorkflowAccessRights u ON w.WorkflowID = u.WorkflowID WHERE u.UserID = %s" % self.user.id)
        
        
    
    def CreateWorkflow(self, WorkflowName, Description):
        w = Workflow.objects.create(WorkflowName=WorkflowName, Description=Description, User_id=self.user.id)
        UserWorkflowAccessRight.objects.create(Workflow_id=w.WorkflowID, User_id=self.user.id, AccessRight_id=objects.AccessRights.Owner)
        return w.WorkflowID
    
    
    
    def UpdateWorkflow(self, WorkflowID, WorkflowName, Description):
        if self.GetUserWorkflowAccess(self.user.id, WorkflowID) <= 2:
            workflow = self.GetWorkflow(WorkflowID)
            workflow.WorkflowName = WorkflowName
            workflow.Description = Description
            workflow.save()
        else:
            raise PermissionDenied
        
    
    
    def DeleteWorkflow(self, WorkflowID):
        if self.GetUserWorkflowAccess(self.user.id, WorkflowID) <= 2:
            workflow = self.GetWorkflow(WorkflowID)
            workflow.delete()
        else:
            raise PermissionDenied
    
    
    
    def GetStages(self, WorkflowID):
        return Stage.objects.filter(Workflow_id=WorkflowID, DeletedInd=False)
    
    
    
    def GetStage(self, StageID):
        try:
            return Stage.objects.get(pk=StageID, DeletedInd=False)
        except Exception, e:
            raise Http404
    
    
    
    def CreateStage(self, StageName, StageTypeID, WorkflowID, Command, StageIndex, Queue="batch", Nodes=1, MaxCores=1, Memory=1, Walltime="2:00:00"):
        stage = Stage.objects.create(StageName=StageName, StageType_id=StageTypeID, Workflow_id=WorkflowID, Command=Command, StageIndex=StageIndex, Queue=Queue, Nodes=Nodes, MaxCores=MaxCores, Memory=Memory, Walltime=Walltime)
        return stage.StageID
        
        
        
    def UpdateStage(self, StageID, StageName, StageTypeID, WorkflowID, Command, StageIndex, Queue="batch", Nodes=1, MaxCores=1, Memory=1, Walltime="2:00:00"):
        stage = self.GetStage(StageID)
        
        stage.StageName = StageName
        stage.StageType_id = StageTypeID
        stage.Workflow_id = WorkflowID
        stage.Command = Command
        stage.StageIndex = StageIndex
        stage.Queue = Queue
        stage.Nodes = Nodes
        stage.MaxCores = MaxCores
        stage.Memory = Memory
        stage.Walltime = Walltime
        stage.save()
            
    
    
    def DeleteStage(self, StageID):
        stage = self.GetStage(StageID)
        stage.delete()
        
    
    
    def GetStageDependencies(self, StageID):
        return StageDependency.objects.filter(StageOI_id=StageID)
        
        
        
    def GetStageDependency(self, StageDependencyID):
        try:
            return StageDependency.objects.get(pk=StageDependencyID)
        except Exception, e:
            raise Http404
    
    
    
    def CreateStageDependency(self, StageID, DependantOnID, ConditionID, ExitCodeValue=None):
        s = StageDependency.objects.create(StageOI_id=StageID, DependantOn_id=DependantOnID, Condition_id=ConditionID, ExitCodeValue=ExitCodeValue)
        return s.StageDependencyID
        
        
        
    def DeleteStageDependency(self, StageDependencyID):
        s = self.GetStageDependency(StageDependencyID)
        s.delete()
        
        
        
    def CreateParameter(self, ParameterName, Context, StageID, ParameterIndex, Delimiter=" ", Value=None, InputBy="user", Multiple=True, Optional=True, ParameterTypeID=1, ParentParameterID=None):
        p = Parameter.objects.create(ParameterName=ParameterName, Context=Context, InputBy=InputBy, Value=Value, Multiple=Multiple, Optional=Optional, ParameterIndex=ParameterIndex, 
                ParameterType_id=ParameterTypeID, Stage_id=StageID, Delimiter=Delimiter, ParentParameter_id=ParentParameterID)
        return p.ParameterID
    
    
    
    def GetParameters(self, StageID):
        return Parameter.objects.filter(Stage_id=StageID, DeletedInd=False)
            
        
            
    def GetParameter(self, ParameterID):
        try:
            return Parameter.objects.get(pk=ParameterID, DeletedInd=False)
        except Exception, e:
            raise Http404
            
    
    
    def DeleteParameter(self, ParameterID):
        param = self.GetParameter(ParameterID)
        param.delete()
    
    
    
    def UpdateParameter(self, ParameterID, ParameterName, Context, StageID, ParameterIndex, Delimiter=" ", Value=None, InputBy="user", Multiple=True, Optional=True, ParameterTypeID=1):
        param = self.GetParameter(ParameterID)
        param.ParameterName = ParameterName
        param.Context = Context
        param.Stage_id = StageID
        param.ParameterIndex = ParameterIndex
        param.Value = Value
        param.InputBy = InputBy
        param.Multiple = Multiple
        param.Optional = Optional
        param.Delimiter = Delimiter
        param.ParameterType_id = ParameterTypeID
        param.save()
        
        
    
    def GetParameterOptions(self, ParameterID):
        return ParameterOption.objects.filter(Parameter_id=ParameterID)
    
    
    
    def GetParameterOption(self, ParameterOptionID):
        try:
            return ParameterOption.objects.get(pk=ParameterOptionID)
        except Exception, e:
            raise Http404
            
    
    
    def CreateParameterOption(self, ParameterOptionText, ParameterOptionValue, ParameterID):
        option = ParameterOption.objects.create(ParameterOptionText=ParameterOptionText, ParameterOptionValue=ParameterOptionValue, Parameter_id=ParameterID)
        return option.Parameter.ParameterID
    
    
    
    def UpdateParameterOption(self, ParameterOptionID, ParameterOptionText, ParameterOptionValue, ParameterID):
        option = self.GetParameterOption(ParameterOptionID)
        option.ParameterOptionText=ParameterOptionText
        option.ParameterOptionValue=ParameterOptionValue
        option.Parameter_id = ParameterID
        option.save()
    
    
    
    def DeleteParameterOption(self, ParameterOptionID):
        option = self.GetParameterOption(ParameterOptionID)
        option.delete()
    
    
    
    def GetExpectedOutput(self, ExpectedOutputID):
        try:
            return ExpectedOutput.objects.get(pk=ExpectedOutputID)
        except Exception, e:
            raise Http404
            
    
    
    def GetExpectedOutputs(self, StageID):
        return ExpectedOutput.objects.filter(Stage__StageID=StageID)
        
        
    
    def CreateExpectedOutput(self, ExpectedOutputFileName, StageID):
        output = ExpectedOutput.objects.create(ExpectedOutputFileName=ExpectedOutputFileName, Stage_id=StageID)
        return output.ExpectedOutputID
        
        
        
    def UpdateExpectedOutput(self, ExpectedOutputID, ExpectedOutputFileName):
        output = self.GetExpectedOutput(ExpectedOutputID)
        output.ExpectedOutputFileName = ExpectedOutputFileName
        output.save()
        
        
        
    def DeleteExpectedOutput(self, ExpectedOutputID):
        output = self.GetExpectedOutput(ExpectedOutputID)
        output.delete()
    
    
    
    def GetUserWorkflowAccess(self, UserID, WorkflowID):
        access_level = objects.AccessRights.No_Access
        
        uwa = UserWorkflowAccessRight.objects.get(User_id=UserID, Workflow_id=WorkflowID)
        access_level = uwa.AccessRight.AccessRightID
            
        return access_level
        
        
    
    def GetUserWorkflowAccessRights(self, WorkflowID):
        return UserWorkflowAccessRight.objects.filter(pk=WorkflowID)
        
        
    
    def GetGroupWorkflowAccessRights(self, WorkflowID):
        return GroupWorkflowAccessRight.objects.filter(pk=WorkflowID)
    
    
    
    def SaveUserWorkflowAccessRight(self, WorkflowID, UserID, AccessRightID):
        if self.GetUserWorkflowAccess(self.user.id, WorkflowID) <= 2:
            access_right = None
            
            with transaction.atomic():
                rights = UserWorkflowAccessRight.objects.filter(Workflow_id=WorkflowID, User_id=UserID)
                if len(rights) >= 1:
                    count = 0
                    for right in rights:
                        if count == 0:
                            right.AccessRight_id = AccessRightID
                            right.save()
                            
                            access_right = right
                        else:
                            right.delete()
                            
                        count += 1
                else:
                    access_right = UserWorkflowAccessRight.objects.create(Workflow_id=WorkflowID, User_id=UserID, AccessRight_id=AccessRightID)
            
            return access_right
        else:
            raise PermissionDenied        
    
    
    
    def DeleteUserWorkflowAccessRight(self, WorkflowID, UserID):
        if self.GetUserWorkflowAccess(self.user.id, WorkflowID) <= 2:
            rights = UserWorkflowAccessRight.objects.filter(Workflow_id=WorkflowID, User_id=UserID)
            for right in rights:
                if right.AccessRight_id != 1:
                    right.delete()
        else:
            raise PermissionDenied
            
    
    
    def SaveGroupWorkflowAccessRight(self, WorkflowID, GroupID, AccessRightID):
        if self.GetUserWorkflowAccess(self.user.id, WorkflowID) <= 2:
            access_right = None
            
            with transaction.atomic():
                rights = GroupWorkflowAccessRight.objects.filter(Workflow_id=WorkflowID, Group_id=GroupID)
                if len(rights) >= 1:
                    count = 0
                    for right in rights:
                        if right.AccessRight_id == 1:
                            raise PermissionDenied
                        
                        if count == 0:
                            right.AccessRight_id = AccessRightID
                            right.save()
                            
                            access_right = right
                        else:
                            right.delete()
                            
                        count += 1
                else:
                    access_right = GroupWorkflowAccessRight.objects.create(Workflow_id=WorkflowID, Group_id=GroupID, AccessRight_id=AccessRightID)
            
            return access_right
        else:
            raise PermissionDenied
    
    
    
    def DeleteGroupWorkflowAccessRight(self, WorkflowID, GroupID):
        if self.GetUserWorkflowAccess(self.user.id, WorkflowID) <= 2:
            rights = GroupWorkflowAccessRight.objects.filter(Workflow_id=WorkflowID, Group_id=GroupID)
            for right in rights:
                right.delete()
        else:
            raise PermissionDenied
    
     
    
    def GetUserJobAccess(self, UserID, JobID):
        access_level = objects.AccessRights.No_Access
        try:
            File.print_to_file("/tmp/accesslevel.txt", "Checking access level %s %s" % (UserID, JobID), 'w')
            uwa = UserJobAccessRight.objects.get(User_id=UserID, Job_id=JobID)
            access_level = uwa.AccessRight_id
            File.print_to_file("/tmp/accesslevel.txt", str(access_level), 'a')
        except Exception, err:
            File.print_to_file("/tmp/accesslevel.txt", str(err), 'a')
            access_level = objects.AccessRights.No_Access
            
        return access_level
    
    
    
    def GetGroupJobAccess(self, GroupID, JobID):
        access_level = objects.AccessRights.No_Access
        try:
            uwa = GroupJobAccessRight.objects.get(Group_id=GroupID, Job_id=JobID)
            access_level = uwa.AccessRight.AccessRightID
        except:
            access_level = objects.AccessRights.No_Access
            
        return access_level
        
        
    
    def GetUserJobAccessRights(self, JobID):
    
        return UserJobAccessRight.objects.filter(pk=JobID)
        
        
    
    def GetGroupJobAccessRights(self, JobID):
        return GroupJobAccessRight.objects.filter(pk=JobID)
    
    
    
    def SaveUserJobAccessRight(self, JobID, UserID, AccessRightID):
        job = Job.objects.get(pk=JobID)
        if self.GetUserJobAccess(self.user.id, JobID) <= 2 and self.GetUserWorkflowAccess(UserID, job.Workflow.WorkflowID) <= 4:            
            access_right = None
            
            with transaction.atomic():
                rights = UserJobAccessRight.objects.filter(Job_id=JobID, User_id=UserID)
                if len(rights) >= 1:
                    count = 0
                    for right in rights:
                        if right.AccessRight_id == 1:
                            raise PermissionDenied
                            
                        if count == 0:
                            right.AccessRight_id = AccessRightID
                            right.save()
                            
                            access_right = right
                        else:
                            right.delete()
                            
                        count += 1
                else:
                    access_right = UserJobAccessRight.objects.create(Job_id=JobID, User_id=UserID, AccessRight_id=AccessRightID)
            
            return access_right
        else:
            raise PermissionDenied
    
    
    
    def DeleteUserJobAccessRight(self, JobID, UserID):
        if self.GetUserJobAccess(self.user.id, JobID) <= 2:
            rights = UserJobAccessRight.objects.filter(Job_id=JobID, User_id=UserID)
            for right in rights:
                if right.AccessRight_id != 1:
                    right.delete()
        else:
            raise PermissionDenied
            
    
    
    def SaveGroupJobAccessRight(self, JobID, GroupID, AccessRightID):
        if self.GetUserJobAccess(self.user.id, JobID) <= 2 and self.GetGroupJobAccess(GroupID, JobID) <= 4:
            access_right = None
            
            with transaction.atomic():
                rights = GroupJobAccessRight.objects.filter(Job_id=JobID, Group_id=GroupID)
                if len(rights) >= 1:
                    count = 0
                    for right in rights:
                        if count == 0:
                            right.AccessRight_id = AccessRightID
                            right.save()
                            
                            access_right = right
                        else:
                            right.delete()
                            
                        count += 1
                else:
                    access_right = GroupJobAccessRight.objects.create(Job_id=JobID, Group_id=GroupID, AccessRight_id=AccessRightID)
            
            return access_right
        else:
            raise PermissionDenied
    
    
    
    def DeleteGroupJobAccessRight(self, JobID, GroupID):
        if self.GetUserJobAccess(self.user.id, JobID) <= 2:
            rights = GroupJobAccessRight.objects.filter(Job_id=JobID, Group_id=GroupID)
            for right in rights:
                right.delete()
        else:
            raise PermissionDenied
            
        
    
    def GetJob(self, JobID):
        if self.GetUserJobAccess(self.user.id, JobID) <= 4:
            return Job.objects.get(pk=JobID)
        else:
            raise Http404              
        
        
        
    def GetJobs(self):
        jobs = Job.objects.raw("SELECT * FROM Jobs j INNER JOIN UserJobAccessRights uj ON j.JobID = uj.JobID WHERE uj.UserID = %s ORDER BY j.JobID DESC" % self.user.id)
        return jobs 
    
    
    
    def GetInputProfile(self, InputProfileID):
        try:
            return InputProfile.objects.get(pk=InputProfileID)
        except Exception, ex:
            raise Http404
            
    
    
    def CreateInputProfile(self, InputProfileName, Description, WorkflowID):
        if self.GetUserWorkflowAccess(self.user.id, WorkflowID) <= 3:
            return InputProfile.objects.create(InputProfileName=InputProfileName, Description=Description, Workflow_id=WorkflowID)
        else:
            raise PermissionDenied
    
    
    
    def UpdateInputProfile(self, InputProfileID, InputProfileName, Description):
        profile = self.GetInputProfile(InputProfileID)
        if self.GetUserWorkflowAccess(self.user.id, profile.Workflow.WorkflowID) <= 3:
            profile.InputProfileName = InputProfileName
            profile.Description = Description  
            profile.save()
             
            return profile         
        else:
            raise PermissionDenied
    
    
    
    def DeleteInputProfile(self, InputProfileID):
        if self.GetUserWorkflowAccess(self.user.id, profile.WorkflowID) <= 3:
            profile = self.GetInputProfile(InputProfileID)
            profile.delete()       
        else:
            raise PermissionDenied
    
    
    
    #unsafe method - if accessed directly through the JMS class, does not check access restrictions
    def GetInputProfileParameter(self, InputProfileParameterID):
        try:
            return InputProfileParameter.objects.get(pk=InputProfileParameterID)
        except Exception, ex:
            raise Http404
            
            
            
    #unsafe method - if accessed directly through the JMS class, does not check access restrictions
    def CreateInputProfileParameter(self, InputProfileID, ParameterID, Value):
        return InputProfileParameter.objects.create(InputProfile_id=InputProfileID, Parameter_id=ParameterID, Value=Value)
            
    
    
    #unsafe method - if accessed directly through the JMS class, does not check access restrictions        
    def DeleteInputProfileParameter(self, InputProfileParameterID):
        param = self.GetInputProfileParameter(InputProfileParameterID)
        param.delete()
    
    
    
    def GetBatchJob(self, BatchJobID):
        try:
            return BatchJob.objects.get(pk=BatchJobID)
        except Exception, err:
            raise Http404
    
    
    
    def GetBatchJobs(self):
        return BatchJobs.objects.raw("SELECT DISTINCT * FROM BatchJobs b INNER JOIN Jobs j ON b.BatchJobID == j.BatchJobID WHERE j.UserID = %s" % self.user.id) 
    
    
    
    def CreateBatchJob(self, BatchJobName, Description):
        return BatchJob.objects.create(BatchJobName=BatchJobName, Description=Description)
    
    
    
    def StartBatchJob(self, BatchJobID):
        batch_job = self.GetBatchJob(BatchJobID)
    
        batch_dir = "%s/%s/jobs/batch_jobs/%s/" % (self.users_dir, self.user.username, str(BatchJobID))
        
        #headers
        WorkflowID = None
        Parameters = []
        
        with open(batch_dir + "batch.jms", 'r') as batch_file:
            header_section = True
            count = 1
            for line in batch_file:
                #after the first occurence of a none header line, no other headers will be considered
                if not line.startswith("#JMS"):
                    header_section = False
                
                if header_section:
                    header = line[4:]
                    header = header.strip()
                    header = header.split("=")
                    if header[0].lower() == "parameters":
                        parameters = header[1].split(",")
                        for p in parameters:
                            Parameters.append(int(p.strip()))
                    elif header[0].lower() == "workflow":
                        WorkflowID = int(header[1].strip())
                    else:
                        print "Ignoring unknown header..."
                else:
                    #after the header section, each line represents a job
                    jobID = self.CreateJobFromBatchFileLine(BatchJobID, WorkflowID, Parameters, line.split("\t"), count)
                    count += 1
                       
                    #start job
                    self.StartJob(jobID)
                        
                        
                        
    def CreateJobFromBatchFileLine(self, BatchJobID, WorkflowID, Parameters, ParameterValues, JobNo):
        user = self.user
        
        if len(Parameters) != len(ParameterValues):
            raise Exception("Job No. %s: Number of parameters is not the same as the number of parameter values.\nNum params: %s\nNum values: %s" % (str(JobNo), str(len(Parameters)), str(len(ParameterValues))))
        
        if self.GetUserWorkflowAccess(user.id, WorkflowID) <= 3:
            workflow = self.GetWorkflow(WorkflowID)
            batch_job = self.GetBatchJob(BatchJobID)
            
            jobID = 0
            with transaction.atomic():
                #create job
                job = self.CreateJob("%s_%s" % (batch_job.BatchJobName, str(JobNo)), WorkflowID, batch_job.Description)
                jobID = job.pk
                
                jobstages = {}
                for s in workflow.Stages.all():
                    #create jobstage
                    jobstage = JobStage.objects.create(Job=job, Stage_id=s.StageID, StageName=s.StageName, RequiresEditInd=False, State_id=objects.Status.Created)
                    jobstages[s.StageID] = jobstage
                    
                index = 0
                batch_dir = "%s/%s/jobs/batch_jobs/%s/files/" % (self.users_dir, self.user.username, str(BatchJobID))   
                job_dir =  "%s/%s/jobs/%s/" % (self.users_dir, self.user.username, str(jobID))             
                for p in Parameters:
                    param = self.GetParameter(ParameterID=p)
                    if param.ParameterType.ParameterTypeID == objects.ParameterType.File:
                        copyfile(batch_dir + ParameterValues[index], job_dir + ParameterValues[index])
                                                      
                    param = JobStageParameter.objects.create(Parameter_id=param.ParameterID, ParameterName=param.ParameterName, JobStage=jobstages[param.Stage.StageID], Value=ParameterValues[index].strip())                    
                    index += 1
                
                return jobID
        else:
            raise PermissionDenied
    
    
    
    def StopBatchJob(self, BatchJobID):
        batch_job = self.GetBatchJob(BatchJobID)
        for job in batch_job.Jobs.all():
            self.StopJob(job.JobID())
    
    
    
    def DeleteBatchJob(self, BatchJobID):
        batch_job = self.GetBatchJob(BatchJobID)
        for job in batch_job.Jobs.all():
            self.StopJob(job.JobID())
            self.DeleteJob(job.JobID())
                
    
    
    def CreateJob(self, JobName, WorkflowID, JobDescription):
        user = self.user
        
        #create job
        job = Job.objects.create(JobName=JobName, JobDescription=JobDescription, Workflow_id=WorkflowID, User_id=user.id, SubmittedAt=datetime.now())              
        jobID = job.pk
        
        #create job directories            
        WorkingDirectory = os.path.join(self.users_dir, user.username + "/jobs/" + str(jobID))
        self.createJobDir(WorkingDirectory)
        LogsDirectory = os.path.join(self.users_dir, user.username + "/jobs/" + str(jobID) + "/Logs")
        self.createJobDir(LogsDirectory)
        
        #copy workflow scripts to job directories
        ScriptDirectory = "%s/workflows/%d" % (self.base_dir, WorkflowID)
        self.RunUserProcess("cp -r %s/* %s" % (ScriptDirectory, WorkingDirectory))
        
        #grant access rights
        UserJobAccessRight.objects.create(User=self.user, Job=job, AccessRight_id=objects.AccessRights.Owner)
        
        return job
        
        
        
    def CreateWorkflowJob(self, JobName, WorkflowID, JobDescription, Stages):    
        user = self.user
        
        if self.GetUserWorkflowAccess(user.id, WorkflowID) <= 3:
            jobID = 0        
            
            with transaction.atomic():
                job = self.CreateJob(JobName, WorkflowID, JobDescription)
                jobID = job.pk
                
                #create jobstages with parameters
                for s in Stages:
                    #create jobstage
                    stage = Stage.objects.get(pk=s.stage_id)
                    jobstage = JobStage.objects.create(Job=job, Stage_id=s.stage_id, StageName=s.stage_name, RequiresEditInd=s.requires_edit, Queue=s.queue,
                        Nodes=s.nodes, MaxCores=s.maxcores, Memory=s.memory, Walltime=s.walltime, State_id=objects.Status.Created)
                
                    #create parameters for jobstage
                    for p in s.parameters:
                        param = self.GetParameter(int(p["ParameterID"]))
                        
                        if param.ParameterType.ParameterTypeID == objects.ParameterType.Complex_Object:
                            #if parameter is "Complex Object", write json to file
                            filename = param.ParameterName.replace(" ", "_").lower() + ".json"
                            File.print_to_file(os.path.join(WorkingDirectory, filename), p["Value"], 'w')
                            p["Value"] = filename
                                
                        param = JobStageParameter.objects.create(Parameter_id=p["ParameterID"], ParameterName=param.ParameterName, JobStage=jobstage, Value=p["Value"])
                    
            return jobID
        else:
            raise PermissionDenied
        
    
    
    def StartJob(self, JobID, StartStage = 1):            
        job = Job.objects.get(pk=JobID)
        
        if self.GetUserWorkflowAccess(self.user.id, job.Workflow.WorkflowID) <= 3:
            workflow = Workflow.objects.get(pk=job.Workflow.WorkflowID)
            
            WorkingDirectory = os.path.join(self.users_dir, job.User.username + "/jobs/" + str(job.JobID))
            LogsDirectory = os.path.join(self.users_dir, job.User.username + "/jobs/" + str(job.JobID) + "/Logs")
            
            #Create job file header - same for all stages in job
            job_file_header = '#!/bin/sh\n'
            job_file_header += '#PBS -V\n'
            job_file_header += '#PBS -W umask=022\n'
            job_file_header += '#PBS -d %s\n' % WorkingDirectory
            
            jobstage_dict = {}
            edit_stages = {}
            count = 1
            for jobstage in job.JobStages.filter(Stage__StageIndex__gte=StartStage).order_by('Stage__StageIndex', 'Stage__StageID'):
                #If stage needs to be paused after completion, add to edit_stages 
                edit_stages[jobstage.Stage.StageID] = jobstage.RequiresEditInd
                
                #Add stage specific parts to job file
                jobstage_specific  = '#PBS -N %s-%s-JMS\n' % (job.JobName.replace(" ", "_"), str(count)) #if the job was submitted via the JMS, the name will end in -<stage_num>-JMS
                jobstage_specific += '#PBS -e localhost:%s\n' % os.path.join(LogsDirectory, 'Stage-%s.err' % str(count))
                jobstage_specific += '#PBS -o localhost:%s\n' % os.path.join(LogsDirectory, 'Stage-%s.out' % str(count))
                jobstage_specific += '#PBS -q %s\n' % jobstage.Queue
                jobstage_specific += '#PBS -l nodes=%s:ppn=%s\n' % (str(jobstage.Nodes), str(jobstage.MaxCores))
                jobstage_specific += '#PBS -l mem=%sgb\n' % str(jobstage.Memory)
                jobstage_specific += '#PBS -l walltime=%s\n' % jobstage.Walltime
                
                #Set stage dependencies
                if len(jobstage.Stage.StageDependencies.all()) > 0:
                    
                    jobstage_specific += '#PBS -W depend='
                    
                    jobstage_ok = ''
                    jobstage_not_ok = ''
                    jobstage_any = ''
                    jobstage_exit_code = ''
                    
                    for dependency in jobstage.Stage.StageDependencies.all():
                        
                        #If the jobstage is dependant on a stage that requires editing, the jobstage must be put in a held state
                        if edit_stages.get(dependency.DependantOn.StageID, False):
                            jobstage_exit_code = '#PBS -h\n'
                        
                        try:                    
                            if dependency.Condition.ConditionID == objects.DependencyCondition.Success:
                                jobstage_ok += ':%s' % jobstage_dict[dependency.DependantOn.StageID]
                            elif dependency.Condition.ConditionID == objects.DependencyCondition.Failed:
                                jobstage_not_ok += ':%s' % jobstage_dict[dependency.DependantOn.StageID]
                            elif dependency.Condition.ConditionID == objects.DependencyCondition.Completed:
                                jobstage_any += ':%s' % jobstage_dict[dependency.DependantOn.StageID]
                            elif dependency.Condition.ConditionID == objects.DependencyCondition.Exit_Code:
                                jobstage_exit_code = '#PBS -h\n'
                        except Exception, e:
                            File.print_to_file("/tmp/dependency_log.err", str(e), 'a')
                    
                    jobstage_deps = ''
                    
                    if len(jobstage_ok) > 0:
                        jobstage_deps += objects.DependencyCondition.GetDependencyType("torque", objects.DependencyCondition.Success) + jobstage_ok
                    
                    if len(jobstage_not_ok) > 0:
                        if len(jobstage_deps) > 0:
                            jobstage_deps+= ','
                            
                        jobstage_deps += objects.DependencyCondition.GetDependencyType("torque", objects.DependencyCondition.Failed) + jobstage_not_ok
                    
                    if len(jobstage_any) > 0:
                        if len(jobstage_deps) > 0:
                            jobstage_deps+= ','
                            
                        jobstage_deps += objects.DependencyCondition.GetDependencyType("torque", objects.DependencyCondition.Completed) + jobstage_any
                        
                    jobstage_specific += '%s\n%s' % (jobstage_deps, jobstage_exit_code)
                
                jobstage_specific += '\n#%s - %s\n' % (job.JobName, jobstage.Stage.StageName)
                
                #Add stage parameters
                parameters = ''
                for param in jobstage.JobStageParameters.all():
                    p = param.Parameter.Context
                    val = param.Value
                    
                    #If parameter type is Previous Parameter, fetch the value of the relevant previous parameter
                    if param.Parameter.ParameterType.ParameterTypeID == objects.ParameterType.Previous_Parameter:
                        prev_param = JobStageParameter.objects.get(Parameter__ParameterID=int(val), JobStage__Job__JobID=job.JobID)
                        val = prev_param.Value
                    
                    if param.Parameter.ParameterType.ParameterTypeID != objects.ParameterType.Boolean:
                        try:
                            #check if the ${VALUE} variable is located in the string
                            num = p.index("${VALUE}")
                            p = p.replace("${VALUE}", val)
                        except Exception, e:
                            #if the ${VALUE} variable is not located in the string, append the value to the end
                            p += " %s" % val                
                    
                    parameters += ' %s' % p
                    
                jobstage_specific += '%s %s' % (jobstage.Stage.Command, parameters)
                
                job_file_data = job_file_header + jobstage_specific
                
                #Write job file
                job_file_path = os.path.join(WorkingDirectory, "job." + str(jobstage.Stage.StageIndex) + ".pbs")
                File.print_to_file(job_file_path, job_file_data, 'w', 0777)
                count += 1
                            
                #Submit to cluster
                qsub_cmd = "qsub %s" % job_file_path
                out = self.RunUserProcess(qsub_cmd)
                
                File.print_to_file("/tmp/submit.txt", out, 'w', 0777)
                
                job_obj = self.GetClusterJobObject(out.strip(), job.User.username)
                self.AddUpdateClusterJob(job_obj)
                
                #Update job details
                jobstage.ClusterJobID = out.strip();
                jobstage.State_id = objects.Status.Queued;
                jobstage.save()
            
                #Store cluster id in dictionary to be used for dependencies of later stages
                jobstage_dict[jobstage.Stage.StageID] = jobstage.ClusterJobID        
        else:
            raise PermissionDenied
    
    
    
    def RepeatJobFromStage(self, JobID, JobName, StageIndex = 0):
        new_job_id = self.CopyJob(JobID, JobName, StageIndex)
        self.StartJob(new_job_id, StageIndex)
        return new_job_id
    
    
    
    def CopyJob(self, JobID, JobName, StageIndex):
        old_job = Job.objects.get(pk=JobID)
        
        if self.GetUserWorkflowAccess(self.user.id, old_job.Workflow.WorkflowID) <= 3 and self.GetUserJobAccess(self.user.id, JobID) <= 3:
            jobID = 0
            with transaction.atomic():   
                User = self.user             
                snapshot_dir = "%s/Snapshots/Stage_%s" % (self.users_dir + old_job.User.username + "/jobs/" + str(JobID), str(StageIndex))
                
                #create job
                new_job = Job.objects.create(JobName=JobName, JobDescription=old_job.JobDescription, Workflow_id=old_job.Workflow.WorkflowID, User_id=User.id, SubmittedAt=datetime.now())              
                working_dir = "%s/jobs/%s" % (self.users_dir + User.username, str(new_job.JobID))
                
                Directory.create_directory(working_dir, 0775)
                
                os.system("cp -r %s/* %s" % (snapshot_dir, working_dir)) 
                os.system("chgrp jms %s -R" % working_dir)
                os.system("chmod 775 %s -R" % working_dir)
                
                #grant access rights
                UserJobAccessRight.objects.create(User=User, Job=new_job, AccessRight_id=objects.AccessRights.Owner)
                
                #create jobstages with parameters
                for s in old_job.JobStages.all():
                    #create jobstage
                    jobstage = JobStage.objects.create(Job=new_job, Stage_id=s.Stage.StageID, StageName=s.StageName, RequiresEditInd=s.RequiresEditInd, State_id=objects.Status.Created)
                
                    #create parameters for jobstage
                    for p in s.JobStageParameters.all():                            
                        param = JobStageParameter.objects.create(Parameter=p.Parameter, ParameterName=p.Parameter.ParameterName, JobStage=jobstage, Value=p.Value)
                
                jobID = new_job.JobID
                    
            return jobID 
        else:
            raise PermissionDenied
    
    
    
    def RunCustomJob(self, JobName, JobDescription, Queue, Nodes, CPUs, Memory, Walltime, Variables, Commands, Files):
        user = self.user
        
        jobID = 0        
            
        with transaction.atomic():
            #create job
            job = Job.objects.create(JobName=JobName, JobDescription=JobDescription, User_id=user.id, SubmittedAt=datetime.now())              
            jobID = job.JobID
                        
            WorkingDirectory = os.path.join(self.users_dir, user.username + "/jobs/" + str(jobID))
            self.createJobDir(WorkingDirectory)    
                
            LogsDirectory = os.path.join(self.users_dir, user.username + "/jobs/" + str(jobID) + "/Logs")
            self.createJobDir(LogsDirectory)
            
            #upload files
            for f in Files:
                full_path = os.path.join(WorkingDirectory, f.name)
                with open(full_path, 'wb+') as destination:
                    for chunk in f.chunks():
                        destination.write(chunk)
            
                #set file permissions
                os.chmod(full_path, 0777)
            
            #grant access rights
            UserJobAccessRight.objects.create(User=user, Job=job, AccessRight_id=objects.AccessRights.Owner)
            
            #create jobstage
            jobstage = JobStage.objects.create(Job=job, StageName="Custom Job", RequiresEditInd=False, Queue=Queue,
                        Nodes=Nodes, MaxCores=CPUs, Memory=Memory, Walltime=Walltime, State_id=objects.Status.Created)
            
            #create job file
            custom_vars = ""
            for v in Variables:
                custom_vars += ",%s=%s" % (v["VariableName"], v["Value"])
            
            job_file = '#!/bin/sh\n'
            job_file += '#PBS -V\n'
            job_file += '#PBS -v WORKING_DIR=%s%s\n' % (WorkingDirectory, custom_vars)
            job_file += '#PBS -W umask=022\n'
            job_file += '#PBS -d %s\n' % WorkingDirectory
            job_file += '#PBS -N %s-JMS\n' % JobName
            job_file += '#PBS -e localhost:%s\n' % os.path.join(LogsDirectory, 'log.err')
            job_file += '#PBS -o localhost:%s\n' % os.path.join(LogsDirectory, 'log.out')
            job_file += '#PBS -q %s\n' % Queue
            job_file += '#PBS -l nodes=%s:ppn=%s\n' % (str(Nodes), str(CPUs))
            job_file += '#PBS -l mem=%sgb\n' % str(Memory)
            job_file += '#PBS -l walltime=%s\n' % Walltime
            
            job_file += "\n\n"
            
            #Add commands, removing Windows-style line endings that can't be handled by qsub
            job_file += Commands.replace('\r\n', '\n')
            
            #Write job file
            job_file_path = os.path.join(WorkingDirectory, "job.pbs")
            File.print_to_file(job_file_path, job_file, 'w', 0777)
                        
            #Submit to cluster
            
            qsub_cmd = "qsub %s" % job_file_path
            out = self.RunUserProcess(qsub_cmd)
            
            #Update job details
            jobstage.ClusterJobID = out.strip();
            jobstage.save()
            
            job_obj = self.GetClusterJobObject(out.strip(), job.User.username)
            self.AddUpdateClusterJob(job_obj)
            
        return jobID

    
    
    def StopJob(self, JobID):
        if self.GetUserJobAccess(self.user.id, JobID) <= 2:
            job = Job.objects.prefetch_related("JobStages").get(pk=JobID, User__id=self.user.id)
            
            for stage in job.JobStages.all():
                self.StopStage(stage.JobStageID)
        else:
            raise PermssionDenied

    
    
    def StopStage(self, JobStageID):
        try:
            File.print_to_file("/tmp/stopstage.txt", "Stopping stage %d" % JobStageID, "a")
            
            stage = JobStage.objects.get(pk=JobStageID)
            stage.State_id = objects.Status.Stopped
            self.StopClusterJob(stage.ClusterJobID)
            stage.save()
            
            File.print_to_file("/tmp/stopstage.txt", "Stopping dependant stages", "a")
            
            #stop dependant stages
            for dependant_stage in JobStage.objects.filter(Job__JobID=stage.Job.JobID, Stage__StageDependencies__DependantOn__StageID=stage.Stage.StageID).distinct():
                self.StopStage(dependant_stage.JobStageID)
            
            File.print_to_file("/tmp/stopstage.txt", "Stopped dependant stages", "a")
        except Exception, err:
            File.print_to_file("/tmp/stopstage.txt", err, "a")

    
    
    def StopClusterJob(self, ID):
        out = self.RunUserProcess("qdel " + ID)
        
        if out.startswith('qdel: Unauthorized Request'):
            raise PermissionDenied
        elif out.startswith('qdel: Unknown Job Id'):
            raise Http404
        elif out.startswith('qdel: Request invalid for state of job'):
            raise Exception
    
        
    
    def DeleteJob(self, JobID):
        if self.GetUserJobAccess(self.user.id, JobID) <= 2:
            try:
                self.StopJob(JobID)
            except PermissionDenied, err:
                raise PermissionDenied
            except Exception, err:
                print str(err)
            
            
            job = Job.objects.get(pk=JobID)
            user = self.user
            
            WorkingDirectory = self.users_dir + user.username + "/jobs/" + str(JobID)
            if os.path.exists(WorkingDirectory):
                cmd = "rm -r " + WorkingDirectory    
                process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
                out, err = process.communicate()
                        
            job.delete()
        else:
            raise PermissionDenied
             
    
    
    def GetFileStream(self, path):
        stream = self.RunUserProcess("cat %s" % path)
        return stream
    
    
    
    def GetClusterJob(self, job_id):
        job = ClusterJob.objects.get(pk=job_id)        
        
        job.OutputStream = self.GetFileStream(job.OutputPath.split(":")[1])
        job.ErrorStream = self.GetFileStream(job.ErrorPath.split(":")[1])
        
        return job
    
    
    
    def GetClusterJobObject(self, job_id, username):
        user = None
        
        try:
            user = User.objects.get(username=username)        
        except Exception, ex:
            user = User.objects.create(username=username)
        
        key = ""
        with open(os.path.dirname(settings.IMPERSONATOR_KEY) + "/pvt.key", "r") as key_file:
            key = key_file.read()
        
        decoded = base64.b64decode(user.filemanagersettings.ServerPass)
        decrypted = PubPvtKey.decrypt(key, decoded)
        credentials = decrypted.split(":")
         
        process = UserProcess(credentials[0], credentials[1])
        out = process.run_command("qstat -x %s" % job_id)
        process.close()
        
        data = objectify.fromstring(out)
        
        return data.Job
        
    
    
    def AddUpdateClusterJob(self, job_obj):
        job = self.ParseClusterJob(job_obj)
        
        #Get user
        username = str(job_obj.Job_Owner).split("@")[0]
        user = User.objects.get(username=username)
        
        #Get job state
        state = objects.Status.Queued
        if job.State == 'Q' or job.State == 'H':
            state = objects.Status.Queued
        elif job.State == 'R':
            state = objects.Status.Running
        elif job.State == 'E' or job.State == 'C':
            state = objects.Status.Completed_Successfully
        
        j = None
        
        #Add the job to the JMS job history if it doesn't exist or update it if it does exist
        try:
            j = JobStage.objects.get(ClusterJobID=job.ClusterJobID) 
        except Exception, ex:
            #If the job doesn't exist, create it (this must happen if the job has been submitted from the terminal)
            #To avoid duplication, jobs submitted via the JMS must be created by the StartJob function and not in this function. We thus exclude jobs ending in -JMS here.
            if not str(job.JobName).endswith("-JMS"):
                with transaction.atomic():
                    j = Job.objects.create(JobName=job.JobName, JobDescription="This job was submitted externally to the JMS", User=user, BatchJobInd=False)
                    JobStage.objects.create(Job=j, ClusterJobID=job.ClusterJobID, State_id=state)
                    
                    UserJobAccessRight.objects.create(User=user, Job=j, AccessRight_id=objects.AccessRights.Owner)
                
                j = None
                
        if j:        
            
            if (j.State.StatusID != state):
                #If the state of the job has changed to completed, run the FinishStage function
                if state == objects.Status.Completed_Successfully:
                    self.FinishStage(job.ClusterJobID, job.ExitStatus)
                #Else just update the sate
                else:
                    j.State_id = state
                    j.save()
        
        return job
    
    
    
    def ParseClusterJob(self, job):
        j = ClusterJob()
        
        j.ClusterJobID = job.Job_Id
        j.JobName = job.Job_Name
        j.JobOwner = job.Job_Owner
        
        #resources requested
        try:
            j.MemoryRequested = job.Resource_List.mem
        except:
            print ""
        try:
            j.NodesAvailable = job.Resource_List.nodect
        except:
            print ""
        try:
            j.NodesRequested = job.Resource_List.nodes
        except:
            print ""
        try:
            j.WalltimeRequested = job.Resource_List.walltime
        except:
            print ""
        
        #resources used
        try:
            j.CPUTimeUsed = job.resources_used.cput
        except:
            print ""
        try:    
            j.MemoryUsed = job.resources_used.mem
        except:
            print ""
        try:
            j.VirtualMemoryUsed = job.resources_used.vmem
        except:
            print ""
        try:
            j.WalltimeUsed = job.resources_used.walltime
        except:
            print ""
        
        #other
        try:
            j.State = job.job_state
        except:
            print ""
        try:
            j.Queue = job.queue
        except:
            print ""
        try:
            j.Server = job.server
        except:
            print ""
        try:
            j.ExecutionHost = str(job.exec_host).split("/")[0]
        except:
            print ""
        try:
            j.SubmitArgs = job.submit_args
        except:
            print ""
        try:
            j.SubmitHost = ""
        except:
            print ""
        try:
            j.OutputPath = job.Output_Path
        except:
            print ""
        try:
            j.ErrorPath = job.Error_Path
        except:
            print ""
        try:
            j.Priority = job.Priority
        except:
            print ""
        
        #time
        try:
            j.CreatedTime = job.ctime
        except:
            print ""
        try:
            j.TimeEnteredQueue = job.qtime
        except:
            print ""
        try:
            j.EligibleTime = job.etime
        except:
            print ""
        try:
            j.LastModified = job.mtime
        except:
            print ""
        try:
            j.StartTime = job.start_time
        except:
            print "No start time available"
        
        #finished
        try:
            j.CompletionTime = job.comp_time
            j.ExitStatus = job.exit_status
            j.TotalRuntime = job.comp_time - job.start_time
        except:
            print "Could not obtain a completion time or exit status as the job is still running."
        
        try:
            j.VariableList = job.Variable_List
        except:
            print "No variable list available"
        try:
            j.Comment = job.comment
        except:
            print "No comment available"
        
        j.save()
        return j
    
    
    def CreateSnapshot(self, job_dir, snap_dir):
        Directory.create_directory(snap_dir, 0775) 
        output = self.RunUserProcess("cp -r %s/* %s" % (job_dir, snap_dir))       
                
                
    
    def GetJobStage(self, JobStageID):
        try:
            jobstage = JobStage.objects.get(pk=JobStageID)
        except:
            raise Http404
            
    
    def FinishStage(self, ClusterJobID, ExitCode):
        try: 
            cluster_job = ClusterJob.objects.get(pk=ClusterJobID)
            cluster_job.State = "C"
            
            try:
                File.print_to_file("/tmp/finish.txt", "%s %s" % (ClusterJobID, str(ExitCode)), "w")
                cluster_job.ExitStatus = ExitCode
                cluster_job.save()
            except Exception, e:
                File.print_to_file("/tmp/finishstage.txt", "ClusterJobID %s\n\n%s" % (ClusterJobID, str(e)), 'a')
            
            jobstage = JobStage.objects.get(ClusterJobID=ClusterJobID)
            self.user = jobstage.Job.User
            
            #If Stage == None, then this was a custom job. Set status to completed successfully if exit code is 0
            if jobstage.Stage == None:
                if ExitCode == 0:
                    jobstage.State_id = objects.Status.Completed_Successfully
                else:
                    jobstage.State_id = objects.Status.Failed
                
                jobstage.save()
            #If RequiresEditInd is set, no dependant jobs will be released until the user has "continued" the stage.
            elif jobstage.RequiresEditInd:
                jobstage.State_id = objects.Status.Awaiting_User_Input
                jobstage.save()
            #If the jobstage has not failed or been stopped, continue the dependant jobs
            elif jobstage.State.StatusID != objects.Status.Failed and jobstage.State.StatusID != objects.Status.Stopped:
                self.ContinueStage(jobstage)
            
        except Exception, e:
            File.print_to_file("/tmp/finishstage.txt", "ClusterJobID %s\n\n%s" % (ClusterJobID, str(e)), 'a')
    
    
    
    def ContinueStage(self, jobstage):
        with open("/tmp/continuestage.txt", 'a') as f:
            try:
                stage_cluster_job = ClusterJob.objects.get(pk=jobstage.ClusterJobID)
                
                #Get all the Jobstages for this Job so that we can loop through them to check if their dependencies have been satisfied
                jobstages = JobStage.objects.filter(Job__JobID=jobstage.Job.JobID).order_by('Stage__StageIndex', 'Stage__StageID')
                
                exit_code_handled = False
                for j in jobstages:
                    #Only check stages that come after the stage currently finishing
                    if j.Stage.StageIndex > jobstage.Stage.StageIndex:
                    
                        #Check exit code dependencies. ALL exit code dependencies must be satisfied for a stage to run. If ONE fails, the stage is cancelled.
                        deps_satisfied = True
                        deps = j.Stage.StageDependencies.all()
                        for dependency in deps:
                            #check all exit code dependencies for a jobstage
                            if dependency.Condition.ConditionID == objects.DependencyCondition.Exit_Code:
                                #get the code that the ClusterJob exited with
                                dep_js = jobstages.get(Stage__StageID=dependency.DependantOn.StageID)
                                cluster_job = ClusterJob.objects.get(pk=dep_js.ClusterJobID)
                                ExitCode = cluster_job.ExitStatus
                                
                                print >> f, "Current:%s, Next:%s, %s %s" % (jobstage.Stage.StageName, j.ClusterJobID, str(ExitCode), str(dependency.ExitCodeValue))
                                
                                if not ExitCode:
                                    #If an exit code is null, the job is still running so the dependency has not been satisfied
                                    deps_satisfied = False
                                    break
                                else:
                                    #if an exit code dependency fails, cancel the stage and all its dependant stages
                                    if dependency.ExitCodeValue != ExitCode:
                                        deps_satisfied = False
                                        if j.State.StatusID != objects.Status.Failed and j.State.StatusID != objects.Status.Stopped:
                                            print >> f, j.StageName + " is being stopped" 
                                            self.StopStage(j.JobStageID)
                                            print >> f, j.StageName + " has been stopped"
                                        else:
                                            print >> f, j.StageName + " has already been stopped"
                                            
                                        break
                                    else:
                                        #if the exit code dependency is met for the stage that is being continued, exit_code_handled can be set to true
                                        if stage_cluster_job.ClusterJobID == cluster_job.ClusterJobID:
                                            exit_code_handled = True
                        
                        #if all of the exit code dependencies have been satisfied, release the job stage
                        if deps_satisfied:
                            print >> f, j.ClusterJobID 
                            self.RunUserProcess("qrls %s" % j.ClusterJobID)
                
                #if the exit code for the stage being continued is non-zero and wasn't handled by one of the dependencies, it means the stage failed
                if stage_cluster_job.ExitStatus != 0 and not exit_code_handled:
                    print >> f, jobstage.StageName + " is being set to failed"
                    jobstage.State_id = objects.Status.Failed
                elif jobstage.State.StatusID != objects.Status.Failed and jobstage.State.StatusID != objects.Status.Stopped:
                    print >> f, jobstage.StageName + " is being set to completed successfully" 
                    jobstage.State_id = objects.Status.Completed_Successfully
                    
                jobstage.save()
                
            except Exception, e:
                print >> f, "JobstageID: %s\n\n%s" % (jobstage.JobStageID, str(e)) 
                jobstage.State_id = objects.Status.Failed
                jobstage.save()
    
    
    
    def UpdateJobState(self, ClusterJobID, StatusID):
        jobstage = JobStage.objects.get(ClusterJobID=ClusterJobID)
        jobstage.State_id = StatusID
        jobstage.save()
        
        #Create snapshot of job at this point in time (if the job was submitted via the JMS)
        if jobstage.Stage != None:
            user = jobstage.Job.User
            
            job_dir = "%s/jobs/%s" % (self.users_dir + user.username, str(jobstage.Job.JobID))
            snap_dir = "%s/Snapshots/Stage_%s" % (job_dir, str(jobstage.Stage.StageIndex))
                    
            self.RunUserProcess("chgrp jms %s -R" % job_dir)
            os.system("chgrp jms %s -R" % job_dir)
                    
            self.CreateSnapshot(job_dir, snap_dir)
        
        
            
    def UpdateJobStatus(self, JobID, StatusID):
        job = Job.objects.get(pk=JobID)
        
        job.Status_id = StatusID
        if(StatusID == Status.Completed_Successfully or StatusID == Status.Stopped or StatusID == Status.Failed):
            job.FinishedAt = datetime.now()
            
        job.save()
    
    
    
    def UpdateJobStatusByJobStageID(self, JobStageID, StatusID):
        jobstage = JobStage.objects.get(pk=JobStageID)
        self.UpdateJobStatus(jobstage.Job.JobID, StatusID)
        
        
    
    def UpdateParameterValue(self, JobStageID, ParameterName, NewValue):
        jsParam = JobStageParameter.objects.get(JobStage__pk=JobStageID, Parameter__ParameterName=ParameterName)    
        jsParam.Value = NewValue
        jsParam.save()
    
    
    
    #Updates a parameter for the next stages of the job
    def UpdateParameterValueFNS(self, CurrentJobStageID, ParameterName, NewValue):        
        jobstage = JobStage.objects.get(pk=CurrentJobStageID)
        jobstages = JobStage.objects.filter(Job__pk=jobstage.Job.JobID)    
        
        for n in jobstages:
            if int(n.JobStageID) > int(CurrentJobStageID):
                self.UpdateParameterValue(n.JobStageID, ParameterName, NewValue)
        
    
    
    def AddResult(self, JobStageID, ResultName, ResultTypeID, ResultData):
        result = JobStageResult.objects.create(JobStage_id=JobStageID, ResultName=ResultName, ResultType_id=ResultTypeID, ResultData=ResultData)
    
    
    
    def GetResults(self, JobStageID, UserID):
        return JobStageResult.objects.filter(JobStage__JobStageID=JobStageID, JobStage__Job__User__id=UserID)
    
    
    
    def GetResultFilePath(self, ResultID, UserID):
        result = JobStageResult.objects.get(pk=ResultID, JobStage__Job__User__id=UserID)
        path = os.path.join(result.JobStage.Job.WorkingDirectory, result.ResultData)
        
        return path
    
    
    
    def UpdateResult(self, ResultID, ResultFileData):
        with transaction.atomic():
            result = JobStageResult.objects.get(pk=ResultID)            
            job = result.JobStage.Job
        
            File.print_to_file(os.path.join(job.WorkingDirectory, result.ResultData), ResultFileData, 'w', 0777)  
    
    
    
    def AddComment(self, JobID, comment, user):
        if self.GetHighestAccessRightForUser(JobID, user) < AccessRights.View:
            Comment.objects.create(User=user, Job_id=JobID, Content=comment)
            return 200
        else:
            return 403
    
    
    
    def DeleteComment(self, CommentID, user):
        comment = Comment.objects.get(pk=CommentID)
        if comment.User.id == user.id or self.GetHighestAccessRightForUser(JobID, user) < AccessRights.View_And_Comment:
            comment.delete()
            return 200
        else:
            return 403            
        
        
    
    def GetComments(self, JobID, user):
        comments = None
        response_code = 200
        
        if self.GetHighestAccessRightForUser(JobID, user) <= AccessRights.View:
            comments = Comment.objects.filter(Job_id=JobID)
        else:
            response_code = 403
        
        return (comments,response_code)
    
    
    
    def SetUserJobAccessRight(self, JobID, AccessRightID, UserID):
        access_rights = UserJobAccessRight.objects.filter(Job__JobID=JobID, User__id=UserID)
        ac = AccessRight.objects.get(pk=AccessRightID)
        
        #if the user doesn't have any rights, create them, else update the user's existing rights
        if len(access_rights) == 0:
            uj = UserJobAccessRight(User_id=UserID, Job_id=JobID, AccessRight_id=AccessRightID)
            uj.save()
            return uj.UserJobAccessRightID;
        else:
            access_rights[0].AccessRight = ac
            access_rights[0].save()
            return access_rights[0].UserJobAccessRightID
    
    
    
    def SetGroupJobAccessRight(self, JobID, AccessRightID, GroupID):
        access_rights = GroupJobAccessRight.objects.filter(Job__JobID=JobID, Group__id=GroupID)
        
        #if the group doesn't have any rights, create them, else update the group's existing rights
        if len(access_rights) == 0:
            gj = GroupJobAccessRight(Group_id=GroupID, Job_id=JobID, AccessRight_id=AccessRightID)
            gj.save()
            return gj.GroupJobAccessRightID;
        else:
            access_rights[0].AccessRight = AccessRight.objects.get(pk=AccessRightID)
            access_rights[0].save()
            return access_rights[0].GroupJobAccessRightID
    
    
    
    def RemoveUserJobAccessRight(self, UserJobAccessRightID):
        UserJobAccessRight.objects.get(pk=UserJobAccessRightID).delete()
    
    
    
    def RemoveGroupJobAccessRight(self, GroupJobAccessRightID):
        GroupJobAccessRight.objects.get(pk=GroupJobAccessRightID).delete()
        
    
    
    def GetHighestAccessRightForUser(self, JobID, user):
        groups = user.groups
        highest_access_right = None
        
        #Check user's access rights
        user_access_rights = user.UserJobAccessRights.filter(Job_id=JobID)
        if len(user_access_rights) > 0:
            highest_access_right = user_access_rights[0].AccessRight
            
        #Check access rights obtained through belonging to groups
        group_access_rights = GroupJobAccessRight.objects.filter(Group__id__in=user.groups.all().values_list('id', flat=True))
        for ac in group_access_rights:
            if ac.AccessRight.AccessRightID < highest_access_right.AccessRightID:
                highest_access_right = ac.AccessRight
        
        return highest_access_right.AccessRightID
    
    
    
    def GetDashboard(self):
        key = ""
        with open(os.path.dirname(settings.IMPERSONATOR_KEY) + "/pvt.key", "r") as key_file:
            key = key_file.read()
        
        decoded = base64.b64decode(self.user.filemanagersettings.ServerPass)
        decrypted = PubPvtKey.decrypt(key, decoded)
        credentials = decrypted.split(":")
         
        return objects.Dashboard(credentials[0], credentials[1])
    
    
    
    def GetServerSettings(self):
        output = self.RunUserProcess('qmgr -c "print server"', expect=self.user.username + "@%s:" % socket.gethostname())
        
        server = objects.TorqueServer()
        admins = {}
        queues = {}
        
        for line in output.split('\n'):
            
            if line.startswith("create queue"):
                
                queue_name = line[13:].strip()
                queues[queue_name] = objects.Queue(QueueName=queue_name)
            
            elif line.startswith("set queue"):
                setting_line = line[10:].split("=")
                
                queue_name = setting_line[0].split(" ")[0]
                queue = queues[queue_name]
                
                setting = setting_line[0].split(" ")[1].strip()
                value = setting_line[1].strip()
                
                
                if setting == "queue_type":
                    queues[queue_name].Type = value
                elif setting == "max_queuable":
                    queues[queue_name].MaxQueable = value
                elif setting == "max_user_queuable":
                    queues[queue_name].MaxUserQueable = value
                elif setting == "max_running":
                    queues[queue_name].MaxRun = value
                elif setting == "max_user_run":
                    queues[queue_name].MaxUserRun = value
                elif setting == "resources_max.mem":
                    queues[queue_name].MaxMemory = value
                elif setting == "resources_max.ncpus":
                    queues[queue_name].MaxCPUs = value
                elif setting == "resources_max.nodes":
                    queues[queue_name].MaxNodes = value
                elif setting == "resources_max.walltime":
                    queues[queue_name].MaxWalltime = value
                elif setting == "resources_default.mem":
                    queues[queue_name].DefaultMemory = value
                elif setting == "resources_default.ncpus":
                    queues[queue_name].DefaultCPUs = value
                elif setting == "resources_default.nodes":
                    queues[queue_name].DefaultNodes = value
                elif setting == "resources_default.walltime":
                    queues[queue_name].DefaultWalltime = value
                elif setting == "enabled":
                    if value.lower() == "true":
                        queues[queue_name].Enabled = True
                    else:
                        queues[queue_name].Enabled = False
                elif setting == "started":
                    if value.lower() == "true":
                        queues[queue_name].Started = True
                    else:
                        queues[queue_name].Started = False
             
            elif line.startswith("set server"):
                setting_line = line[11:].split("=")
                
                setting = setting_line[0].strip()
                value = setting_line[1].strip()
                
                if setting == "scheduling":
                    if value.lower() == "true":
                        server.Scheduling = True
                    else:
                        server.Scheduling = False
                elif setting == "acl_hosts":
                    server.ServerName = value
                elif setting == "managers" or setting == "managers +":
                    if value in admins:
                        admins[value].Manager = True
                    else:
                        admins[value] = objects.ServerAdministrator(Username=value.split("@")[0], Host=value.split("@")[1], Manager=True)
                elif setting == "operators" or setting == "operators +":
                    if value in admins:
                        admins[value].Operator = True
                    else:
                        admins[value] = objects.ServerAdministrator(Username=value.split("@")[0], Host=value.split("@")[1], Operator=True)
                elif setting == "default_queue":
                    queues[value].DefaultQueue = True
                elif setting == "query_other_jobs":
                    if value.lower() == "true":
                        server.QueryOtherJobs = True
                    else:
                        server.QueryOtherJobs = False
                elif setting == "scheduler_iteration":
                    server.SchedularIteration = value
                elif setting == "node_check_rate":
                    server.NodeCheckRate = value
                elif setting == "tcp_timeout":
                    server.TCPTimeout = value
                elif setting == "job_stat_rate":
                    server.JobStatRate = value
                elif setting == "mom_job_sync":
                    if value.lower() == "true":
                        server.MOMJobSync = True
                    else:
                        server.MOMJobSync = False
                elif setting == "keep_completed":
                    server.KeepCompleted = value
                elif setting == "moab_array_compatible":
                    if value.lower() == "true":
                        server.MoabArrayCompatible = True
                    else:    
                        server.MoabArrayCompatible = False
        
        server.ServerAdministrators = []           
        for k in admins:
            server.ServerAdministrators.append(admins[k])
        
        server.Queues = []  
        for k in queues:
            server.Queues.append(queues[k])
        
        return server
        
        
        
    def UpdateServerSettings(self, KeepCompleted, JobStatRate, SchedularIteration, NodeCheckRate, TCPTimeout, QueryOtherJobs, MOMJobSync, MoabArrayCompatible, Scheduling):
        output = self.RunUserProcess('qmgr -c "set server keep_completed = %s"' % str(KeepCompleted))
        output += "\n" + self.RunUserProcess('qmgr -c "set server job_stat_rate = %s"' % str(JobStatRate))
        output += "\n" + self.RunUserProcess('qmgr -c "set server scheduler_iteration = %s"' % str(SchedularIteration))
        output += "\n" + self.RunUserProcess('qmgr -c "set server node_check_rate = %s"' % str(NodeCheckRate))
        output += "\n" + self.RunUserProcess('qmgr -c "set server tcp_timeout = %s"' % str(TCPTimeout))
        output += "\n" + self.RunUserProcess('qmgr -c "set server query_other_jobs = %s"' % str(QueryOtherJobs))
        output += "\n" + self.RunUserProcess('qmgr -c "set server mom_job_sync = %s"' % str(MOMJobSync))
        output += "\n" + self.RunUserProcess('qmgr -c "set server moab_array_compatible = %s"' % str(MoabArrayCompatible))
        output += "\n" + self.RunUserProcess('qmgr -c "set server scheduling = %s"' % str(Scheduling))
        
        return output
        
    
    
    def CreateQueue(self, QueueName):       
        output = self.RunUserProcess('qmgr -c "create queue %s"' % QueueName)
        
    
    
    def DeleteQueue(self, QueueName):       
        output = self.RunUserProcess('qmgr -c "delete queue %s"' % QueueName)
        
                
    
    def UpdateQueue(self, QueueName, Type=None, Enabled=None, Started=None, MaxQueable=None, MaxRun=None, MaxUserQueable=None, MaxUserRun=None, MaxNodes=None, DefaultNodes=None, MaxCPUs=None, DefaultCPUs=None, MaxMemory=None, DefaultMemory=None, MaxWalltime=None, DefaultWalltime=None, DefaultQueue=False):
        output = ""
        
        if Type != None:
            output += self.RunUserProcess('qmgr -c "set queue %s %s = %s"' % (QueueName, "queue_type", str(Type)))
        if Started != None:
            output += "\n" + self.RunUserProcess('qmgr -c "set queue %s %s = %s"' % (QueueName, "started", str(Started)))
        if MaxQueable != None:
            output += "\n" + self.RunUserProcess('qmgr -c "set queue %s %s = %s"' % (QueueName, "max_queuable", str(MaxQueable)))
        if MaxRun != None:
            output += "\n" + self.RunUserProcess('qmgr -c "set queue %s %s = %s"' % (QueueName, "max_running", str(MaxRun)))
        if MaxUserQueable != None:
            output += "\n" + self.RunUserProcess('qmgr -c "set queue %s %s = %s"' % (QueueName, "max_user_queuable", str(MaxUserQueable)))
        if MaxUserRun != None:
            output += "\n" + self.RunUserProcess('qmgr -c "set queue %s %s = %s"' % (QueueName, "max_user_run", str(MaxUserRun)))
        if MaxNodes != None:
            output += "\n" + self.RunUserProcess('qmgr -c "set queue %s %s = %s"' % (QueueName, "resources_max.nodes", str(MaxNodes)))
        if DefaultNodes != None:
            output += "\n" + self.RunUserProcess('qmgr -c "set queue %s %s = %s"' % (QueueName, "resources_default.nodes", str(DefaultNodes)))
        if MaxCPUs != None:
            output += "\n" + self.RunUserProcess('qmgr -c "set queue %s %s = %s"' % (QueueName, "resources_max.ncpus", str(MaxCPUs)))
        if DefaultCPUs != None:
            output += "\n" + self.RunUserProcess('qmgr -c "set queue %s %s = %s"' % (QueueName, "resources_default.ncpus", str(DefaultCPUs)))
        if MaxMemory != None:
            output += "\n" + self.RunUserProcess('qmgr -c "set queue %s %s = %s"' % (QueueName, "resources_max.mem", str(MaxMemory)))
        if DefaultMemory != None:
            output += "\n" + self.RunUserProcess('qmgr -c "set queue %s %s = %s"' % (QueueName, "resources_default.mem", str(DefaultMemory)))
        if MaxWalltime != None:
            output += "\n" + self.RunUserProcess('qmgr -c "set queue %s %s = %s"' % (QueueName, "resources_max.walltime", str(MaxWalltime)))
        if DefaultWalltime != None:
            output += "\n" + self.RunUserProcess('qmgr -c "set queue %s %s = %s"' % (QueueName, "resources_default.walltime", str(DefaultWalltime)))
        if Enabled != None:
            output += "\n" + self.RunUserProcess('qmgr -c "set queue %s %s = %s"' % (QueueName, "enabled", str(Enabled)))
    
    
    
    def SaveAdministrator(self, Administrators):
        output = self.RunUserProcess('qmgr -c "set server managers = %s@%s"' % (self.user.username, Administrators[0].Host))
        output += self.RunUserProcess('qmgr -c "set server operators = %s@%s"' % (self.user.username, Administrators[0].Host))
        
        for a in Administrators:
            if a.Manager:
                output += "\n" + self.RunUserProcess('qmgr -c "set server managers += %s@%s"' % (a.Username, a.Host))
            if a.Operator:
                output += "\n" + self.RunUserProcess('qmgr -c "set server operators += %s@%s"' % (a.Username, a.Host))
    
    
    
    def GetNodes(self): 
        out = self.RunUserProcess("qnodes -x")
        
        nodes = []        
        
        root = ET.fromstring(out)
        
        for node in root.iter('Node'):
            name = node.find('name').text
            state = node.find('state').text
            num_cores = int(node.find('np').text)
            try:
                properties = node.find('properties').text
            except Exception, ex:
                properties = ""
                
            n = objects.Client(name, state, num_cores, properties)
            
            nodes.append(n)
        
        return nodes
    
    
    
    def AddNode(self, NodeName, NumProcessors, Properties, IPAddress):   
        output = self.RunUserProcess('qmgr -c "create node %s"' % NodeName)   
        if NumProcessors:
            output += self.RunUserProcess('qmgr -c "set node %s np = %s"' % (NodeName, str(NumProcessors)))
        if Properties:
            output += self.RunUserProcess('qmgr -c "set node %s properties = %s"' % (NodeName, Properties))
             
        output += self.RestartTorqueServer()
    
    
    
    def UpdateNode(self, NodeName, NumProcessors, Properties):    
        output = self.RunUserProcess('qmgr -c "set node %s np = %s"' % (NodeName, str(NumProcessors)))
        output += self.RunUserProcess('qmgr -c "set node %s properties = %s"' % (NodeName, Properties))
    
    
    
    def DeleteNode(self, NodeName):   
        output = self.RunUserProcess('qmgr -c "delete node %s"' % NodeName) 
        output += self.RestartTorqueServer()    
        
    
    
    def RestartTorqueServer(self):
        output = self.RunUserProcess("sudo service pbs_server restart", expect=": ", timeout=40) 
        output = self.RunUserProcess(self.user.filemanagersettings.ServerPass, timeout=60)
        return output
                       
        
        
    def createJobDir(self, directory):
        self.RunUserProcess("mkdir -p %s" % directory)
        self.RunUserProcess("chmod 777 %s -R" % directory)
